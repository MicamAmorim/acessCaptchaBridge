import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import providers


class ProviderTests(unittest.TestCase):
    def test_ollama_only_installed_vision_models(self):
        def fake_fetch(url, data=None, timeout=2):
            if url.endswith('/api/tags'):
                return {'models': [{'name': 'qwen3-vl:4b'}, {'name': 'llama3.2:3b'}, {'name': 'qwen3-vl:4b'}]}
            self.assertIn('model', data)
            return {'capabilities': ['completion', 'vision'] if data['model'] == 'qwen3-vl:4b' else ['completion']}
        with patch.object(providers, '_fetch_json', fake_fetch):
            self.assertEqual(providers.ollama_models(), [{'provider': 'ollama', 'id': 'qwen3-vl:4b', 'label': 'qwen3-vl:4b'}])

    def test_ollama_offline_hides_provider(self):
        with patch.object(providers, '_fetch_json', side_effect=OSError('offline')):
            self.assertEqual(providers.ollama_models(), [])

    def test_codex_only_when_cli_present_and_model_has_image(self):
        entries = [
            {'model': 'gpt-6.1-sol', 'displayName': 'GPT-6.1 Sol', 'inputModalities': ['text', 'image']},
            {'model': 'text-only', 'inputModalities': ['text']},
            {'model': 'hidden', 'hidden': True},
        ]
        with patch.object(providers, 'find_codex', return_value=None):
            self.assertEqual(providers.codex_models(), [])
        with patch.object(providers, 'find_codex', return_value='/example/codex'), patch.object(providers, '_codex_rpc', return_value=entries):
            self.assertEqual(providers.codex_models(), [{'provider': 'codex', 'id': 'gpt-6.1-sol', 'label': 'GPT-6.1 Sol'}])

    def test_codex_rpc_real_stdio_handshake(self):
        # A fake executable tests the JSONL handshake without installing Codex.
        with tempfile.TemporaryDirectory() as dirname:
            script = Path(dirname, 'fake_codex.py')
            script.write_text('''import json,sys
for line in sys.stdin:
    obj = json.loads(line)
    if obj.get('method') == 'initialize':
        print(json.dumps({'id': obj['id'], 'result': {'userAgent': 'fake'}}), flush=True)
    if obj.get('method') == 'model/list':
        print(json.dumps({'id': obj['id'], 'result': {'data': [{'model': 'vision-test', 'inputModalities': ['image']}], 'nextCursor': None}}), flush=True)
''', encoding='utf-8')
            with patch.object(providers, '_codex_command', side_effect=lambda executable, *args: [sys.executable, str(script), *args]):
                found = providers._codex_rpc('fake', timeout=5)
            self.assertEqual(found[0]['model'], 'vision-test')

    def test_selection_rejects_unavailable_or_injected_names(self):
        sample = {'models': [{'provider': 'ollama', 'id': 'vision:4b', 'label': 'Vision'}]}
        with patch.object(providers, 'available_models', return_value=sample):
            providers.assert_available('ollama', 'vision:4b')
            for provider, name in [('codex', 'vision:4b'), ('ollama', 'not-installed'), ('ollama', ';evil')]:
                with self.assertRaises(ValueError):
                    providers.assert_available(provider, name)

    def test_model_list_groups_only_detected(self):
        with patch.object(providers, 'ollama_models', return_value=[]), patch.object(providers, 'codex_models', return_value=[{'provider': 'codex', 'id': 'vision', 'label': 'Vision'}]):
            result = providers.available_models(force=True)
        self.assertFalse(result['providers']['ollama']['available'])
        self.assertTrue(result['providers']['codex']['available'])
        self.assertEqual(len(result['models']), 1)


if __name__ == '__main__':
    unittest.main()

class CodexExecutionTests(unittest.TestCase):
    def test_codex_uses_image_and_cleans_temp_dir(self):
        import base64
        with tempfile.TemporaryDirectory() as dirname:
            fake = Path(dirname, 'fake_codex_exec.py')
            fake.write_text('''import pathlib,sys
args = sys.argv[1:]
assert args[:3] == ['-c', 'approval_policy="never"', 'exec']
assert '--sandbox' in args and args[args.index('--sandbox')+1] == 'read-only'
assert '--ask-for-approval' not in args
assert args[-1] == '-'
assert 'não utilize comandos' in sys.stdin.read().lower()
screenshot = pathlib.Path(args[args.index('--image')+1])
assert screenshot.is_file() and screenshot.read_bytes().startswith(b'\\xff\\xd8\\xff')
pathlib.Path(args[args.index('--output-last-message')+1]).write_text('Controle de áudio identificado.', encoding='utf-8')
''', encoding='utf-8')
            model = 'vision-test'
            shot = base64.b64encode(b'\xff\xd8\xff' + b'0' * 200).decode()
            with patch.object(providers, 'find_codex', return_value='/fake/codex'), patch.object(providers, '_codex_command', side_effect=lambda executable, *args: [sys.executable, str(fake), *args]):
                response = providers.codex_describe(shot, model, 'Olhe controles.', 'Não compartilhe segredos.')
            self.assertEqual(response, 'Controle de áudio identificado.')

    def test_codex_cli_error_is_actionable_without_exposing_raw_stderr(self):
        import base64
        with tempfile.TemporaryDirectory() as dirname:
            fake = Path(dirname, 'failing_codex.py')
            fake.write_text('''import sys
sys.stderr.write("error: unexpected argument '--bad-flag' found\\n")
sys.exit(2)
''', encoding='utf-8')
            shot = base64.b64encode(b'\xff\xd8\xff' + b'0' * 200).decode()
            with patch.object(providers, 'find_codex', return_value='/fake/codex'), patch.object(providers, '_codex_command', side_effect=lambda executable, *args: [sys.executable, str(fake), *args]):
                with self.assertRaisesRegex(RuntimeError, 'rejeitou um argumento'):
                    providers.codex_describe(shot, 'vision-test', 'Descreva a imagem.', 'Proteja dados.')
