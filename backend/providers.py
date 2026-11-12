"""Discover locally available image-capable models; dispatch accessibility analysis.

- Ollama: only installed models with the `vision` capability.
- Codex: only when its local CLI is on PATH and its app-server responds to
  `model/list`; a catalog entry does not prove account entitlement.
No provider is downloaded, enabled, or installed by this module.
"""
from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OLLAMA_BASE = 'http://127.0.0.1:11434'
MODEL_ID = re.compile(r'^[A-Za-z0-9_.:/-]{1,100}$')
CODEX_TIMEOUT = 140

# Short TTL balances GUI responsiveness with detecting a newly installed model.
_cache_lock = threading.Lock()
_model_cache: tuple[float, dict] | None = None


def _fetch_json(url: str, data: dict | None = None, timeout: float = 2.0) -> dict:
    payload = None if data is None else json.dumps(data).encode('utf-8')
    request = Request(url, data=payload, headers={'Content-Type': 'application/json'} if data is not None else {}, method='POST' if data is not None else 'GET')
    with urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if not isinstance(result, dict):
        raise ValueError('Resposta inválida de serviço local.')
    return result


def ollama_models() -> list[dict]:
    """Use installed /api/tags and /api/show, not a global model catalog."""
    try:
        tags = _fetch_json(OLLAMA_BASE + '/api/tags', timeout=2)
    except (URLError, HTTPError, TimeoutError, OSError, ValueError):
        return []
    names, seen = [], set()
    for item in tags.get('models', [])[:100]:
        if not isinstance(item, dict):
            continue
        name = item.get('name') or item.get('model')
        if isinstance(name, str) and MODEL_ID.fullmatch(name) and name not in seen:
            seen.add(name)
            names.append(name)

    def is_vision(name):
        try:
            show = _fetch_json(OLLAMA_BASE + '/api/show', {'model': name}, timeout=2)
        except (URLError, HTTPError, TimeoutError, OSError, ValueError):
            return False
        return 'vision' in (show.get('capabilities') or [])

    with ThreadPoolExecutor(max_workers=8) as pool:
        status = list(pool.map(is_vision, names))
    return [
        {'provider': 'ollama', 'id': name, 'label': name}
        for name, visual in zip(names, status) if visual
    ]


def find_codex() -> str | None:
    """A desktop Codex installation does not imply a callable CLI."""
    return shutil.which('codex')


def _codex_command(executable: str, *args: str) -> list[str]:
    # On Windows the npm distribution commonly exposes codex.cmd; avoid shell=True.
    if os.name == 'nt' and executable.lower().endswith(('.cmd', '.bat')):
        return [os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c', f'"{executable}"', *args]
    return [executable, *args]


def _codex_rpc(executable: str, timeout: float = 12) -> list[dict]:
    """One short-lived, request-only Codex app-server session for model/list.

    No Codex thread or inference is started while detecting installed providers.
    """
    process = subprocess.Popen(
        _codex_command(executable, 'app-server'),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding='utf-8', errors='replace', bufsize=1,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    responses: queue.Queue = queue.Queue()
    def reader():
        try:
            for line in process.stdout:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        responses.put(item)
                except json.JSONDecodeError:
                    continue
        except (OSError, ValueError):
            pass
        responses.put({'_ended': True})

    threading.Thread(target=reader, daemon=True).start()
    start = time.monotonic()
    def send(data):
        process.stdin.write(json.dumps(data, ensure_ascii=False) + '\n')
        process.stdin.flush()

    def receive(request_id):
        while time.monotonic() - start < timeout:
            try:
                event = responses.get(timeout=max(0.05, timeout - (time.monotonic() - start)))
            except queue.Empty:
                break
            if event.get('_ended'):
                break
            if event.get('id') == request_id:
                if event.get('error'):
                    raise RuntimeError('Codex não retornou o catálogo de modelos.')
                return event.get('result', {})
        raise TimeoutError('Codex não respondeu à consulta de modelos.')

    found = []
    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'acessoponte', 'title': 'AcessoPonte', 'version': '0.2.0'}
        }})
        receive(1)
        send({'method': 'initialized', 'params': {}})
        cursor = None
        for page in range(5):
            params = {'limit': 100, 'includeHidden': False}
            if cursor:
                params['cursor'] = cursor
            request_id = 2 + page
            send({'id': request_id, 'method': 'model/list', 'params': params})
            result = receive(request_id)
            if not isinstance(result, dict):
                break
            found.extend(result.get('data', []))
            cursor = result.get('nextCursor')
            if not cursor:
                break
        return found
    finally:
        try:
            process.stdin.close()
        except (OSError, ValueError, AttributeError):
            pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        try:
            process.stdout.close()
        except (OSError, ValueError, AttributeError):
            pass


def codex_models() -> list[dict]:
    executable = find_codex()
    if not executable:
        return []
    try:
        entries = _codex_rpc(executable)
    except (OSError, ValueError, TimeoutError, RuntimeError, subprocess.SubprocessError):
        return []
    found, seen = [], set()
    for item in entries:
        if not isinstance(item, dict) or item.get('hidden'):
            continue
        model = item.get('model') or item.get('id')
        if not isinstance(model, str) or not MODEL_ID.fullmatch(model) or model in seen:
            continue
        modalities = item.get('inputModalities', ['text', 'image'])
        if not isinstance(modalities, list) or 'image' not in modalities:
            continue
        seen.add(model)
        label = item.get('displayName')
        found.append({'provider': 'codex', 'id': model, 'label': str(label)[:90] if label else model})
    return found


def available_models(force: bool = False) -> dict:
    global _model_cache
    with _cache_lock:
        if not force and _model_cache and time.monotonic() - _model_cache[0] < 30:
            return _model_cache[1]
        with ThreadPoolExecutor(max_workers=2) as pool:
            ollama_future = pool.submit(ollama_models)
            codex_future = pool.submit(codex_models)
            ollama = ollama_future.result()
            codex = codex_future.result()
        result = {'providers': {
            'ollama': {'available': bool(ollama), 'models': ollama},
            'codex': {'available': bool(codex), 'models': codex},
        }, 'models': ollama + codex}
        _model_cache = (time.monotonic(), result)
        return result


def assert_available(provider: str, model: str) -> None:
    if provider not in ('ollama', 'codex') or not isinstance(model, str) or not MODEL_ID.fullmatch(model):
        raise ValueError('Provedor ou modelo inválido.')
    # Force fresh discovery before sending a confidential screenshot to a provider.
    if not any(m['id'] == model and m['provider'] == provider for m in available_models(force=True)['models']):
        raise ValueError('Modelo indisponível. Atualize a lista e escolha um modelo instalado ou acessível.')


def codex_describe(image_b64: str, model: str, prompt: str, system_prompt: str) -> str:
    executable = find_codex()
    if not executable:
        raise ValueError('O Codex CLI não foi encontrado neste computador.')
    # codex exec -i needs an image path. It exists temporarily and is removed
    # as soon as the CLI exits. Codex itself may log activity depending on config.
    with tempfile.TemporaryDirectory(prefix='acessoponte-codex-') as directory:
        temp_dir = Path(directory)
        image_bytes = base64.b64decode(image_b64)
        screenshot = temp_dir / ('captura.png' if image_bytes.startswith(b'\x89PNG') else 'captura.jpg')
        screenshot.write_bytes(image_bytes)
        result_file = temp_dir / 'resposta.txt'
        instruction = (
            system_prompt + '\n\n' + prompt + '\n\n'
            'Somente descreva. Não utilize comandos, arquivos adicionais, plugins, '
            'ferramentas, navegação web ou alterações de configuração.'
        )
        # codex exec rejects --ask-for-approval as a subcommand option.
        # Use the documented global config override to disable prompts.
        args = _codex_command(
            executable, '-c', 'approval_policy="never"',
            'exec', '--ephemeral', '--skip-git-repo-check',
            '--sandbox', 'read-only',
            '--model', model,
            '--image', str(screenshot), '--output-last-message', str(result_file), '-',
        )
        try:
            outcome = subprocess.run(
                # Explicit UTF-8 bytes avoid the Windows default ANSI code page.
                args, cwd=directory, input=instruction.encode('utf-8'),
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=CODEX_TIMEOUT, check=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            )
        except subprocess.TimeoutExpired:
            raise TimeoutError('Codex excedeu o tempo de 140 segundos.') from None
        if outcome.returncode:
            # Keep raw CLI logs local: they can contain file paths or
            # user-specific data and should not be sent to the browser.
            details = (outcome.stderr or b'').decode('utf-8', errors='replace').strip()
            if details:
                print('[AcessoPonte] Falha Codex CLI (stderr, últimos 1200 caracteres):\n'
                      + details[-1200:], flush=True)
            lower = details.lower()
            if 'not valid utf-8' in lower or 'invalid utf-8' in lower:
                hint = 'Codex rejeitou a codificação UTF-8. Atualize o backend e tente novamente.'
            elf any(term in lower for term in ('unexpected argument', 'unrecognized option', 'unknown option')):
                hint = 'O Codex CLI rejeitou um argumento. Confira a versão e a sintaxe do comando.'
            elif any(term in lower for term in ('authentication', 'unauthorized', 'login required', '401', 'api key')):
                hint = 'O Codex indicou falha de autenticação; execute codex login status no terminal.'
            elif any(term in lower for term in ('model not found', 'unsupported model', 'model does not exist')):
                hint = 'O modelo selecionado não está disponível para esse provedor Codex.'
            else:
                hint = 'Consulte a mensagem de erro no terminal onde o servidor AcessoPonte está aberto.'
            raise RuntimeError(f'Codex retornou código {outcome.returncode}. {hint}')
        try:
            description = result_file.read_text('utf-8').strip()
        except OSError:
            raise RuntimeError('Codex não retornou uma descrição.') from None
        if not description:
            raise RuntimeError('Codex retornou uma descrição vazia.')
        return description[:20000]
