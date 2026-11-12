import base64
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import server


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.AppHandler.token = 'A' * 32
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.AppHandler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()
        cls.root = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, body=None, token=True, origin='chrome-extension://' + 'a' * 32):
        headers = {'Origin': origin}
        if token:
            headers['Authorization'] = 'Bearer ' + 'A' * 32
        if body is not None:
            headers['Content-Type'] = 'application/json'
        return Request(self.root + path, data=None if body is None else json.dumps(body).encode(), headers=headers,
                       method='POST' if body is not None else 'GET')

    def test_providers_endpoint_requires_token(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.request('/models', token=False), timeout=2)
        self.assertEqual(ctx.exception.code, 401)

    def test_providers_endpoint_rejects_external_page_origin(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.request('/models', origin='https://malicious.example'), timeout=2)
        self.assertEqual(ctx.exception.code, 401)

    def test_providers_returns_only_detected_catalog(self):
        catalog = {'models': [{'provider': 'ollama', 'id': 'visual:4b', 'label': 'Visual'}],
                   'providers': {'ollama': {'available': True}}}
        with patch.object(server, 'available_models', return_value=catalog):
            with urlopen(self.request('/models'), timeout=2) as resp:
                self.assertEqual(json.load(resp)['models'], catalog['models'])

    def test_codex_requires_separate_consent(self):
        shot = base64.b64encode(b'\xff\xd8\xff' + b'1' * 200).decode()
        body = {'image': shot, 'provider': 'codex', 'model': 'vision', 'scan': {}}
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.request('/analyze', body), timeout=2)
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn('Autorize', ctx.exception.read().decode('utf-8'))

    def test_valid_dispatch_uses_selected_provider_and_sanitized_scan(self):
        shot = base64.b64encode(b'\xff\xd8\xff' + b'1' * 200).decode()
        body = {'image': shot, 'provider': 'codex', 'model': 'vision', 'confirmRemote': True,
                'scan': {'site': 'portal.gov', 'secret': 'do not forward'}}
        with patch.object(server, 'assert_available') as check, patch.object(server, 'describe', return_value='Atalho acessível.') as describe:
            with urlopen(self.request('/analyze', body), timeout=2) as resp:
                result = json.load(resp)
        check.assert_called_once_with('codex', 'vision')
        self.assertEqual(result['provider'], 'codex')
        self.assertNotIn('secret', result['scan'])
        self.assertEqual(describe.call_args.kwargs['provider'], 'codex')


if __name__ == '__main__':
    unittest.main()
