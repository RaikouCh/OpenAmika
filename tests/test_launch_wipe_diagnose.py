"""launch.py --wipe-memory, --diagnose and the "why did it not start" rows (2026-11-09, items 49 and 33). Offline:
temporary checkouts, stand-ins for her brain and gateway on free ports, no GPU or PowerShell calls."""
import contextlib
import http.server
import json
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from test_launch_preflight import example_cfg, free_port, launch
from test_wipe_busy import crash_mid_turn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'brain'))
from f_memory import MemoryRuntime  # noqa: E402
from f_usage import UsageMeter  # noqa: E402

FAKE_KEY = 'sk-or-v1-' + 'f' * 48


@pytest.fixture()
def checkout(tmp_path, monkeypatch):
    """launch.py looking at a temporary OpenAmika folder with her memory, a transcript and a log."""
    for name, value in (('ROOT', tmp_path), ('LOGS', tmp_path / 'logs'), ('PREFLIGHT', tmp_path / 'logs' / 'preflight.json'),
                        ('INSTANCE', tmp_path / 'logs' / 'instance.json'), ('TTS_ENGINE', tmp_path / 'vendor' / 'tts-engine'),
                        ('AVATAR_MODELS', tmp_path / 'avatar' / 'models')):
        monkeypatch.setattr(launch, name, value)
    monkeypatch.setattr(launch, 'list_processes', lambda: [])
    monkeypatch.setattr(launch, 'listeners', lambda: {})
    monkeypatch.setattr(launch, 'gpu_info', lambda: [{'name': 'RTX Test 8GB', 'driver': '999.1', 'total_mb': 8192,
                                                      'used_mb': 6000, 'free_mb': 2192}])
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config' / 'build_f.json').write_text(json.dumps({'memory_profile': 'live'}), 'utf-8')
    memory = MemoryRuntime(tmp_path / 'memory_f' / 'live')
    memory.archive({'id': 'e1', 'time': '2026-11-01T10:00:00Z', 'user': 'My cat is Miso.', 'assistant': 'Cute!',
                    'source_kind': 'conversation'})
    memory.close()
    context = tmp_path / 'brain' / 'memories'
    context.mkdir(parents=True)
    (context / 'conversations.json').write_text(json.dumps({'turns': [{'user': 'My cat is Miso.'}]}), 'utf-8')
    return tmp_path


@contextlib.contextmanager
def stand_in(port, answers, seen):
    """A local service: GET path -> dict; POST path -> a list of (status, dict) answered in turn; requests in seen."""
    class Handler(http.server.BaseHTTPRequestHandler):
        def reply(self, status, payload):
            data = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path in answers:
                self.reply(200, answers[self.path])
            else:
                self.reply(404, {})

        def do_POST(self):  # noqa: N802
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
            seen.append((self.path, dict(self.headers), body))
            status, payload = answers[('POST', self.path)].pop(0)
            self.reply(status, payload)

        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def ports_cfg():
    return {'brain_port': free_port(), 'chat_port': free_port()}


def test_wipe_memory_while_she_is_not_running_backs_up_then_wipes_on_disk(checkout):
    ledger = checkout / 'memory_f' / 'usage.sqlite'
    crash_mid_turn(ledger)                                   # her last run died mid-answer
    out = []
    assert launch.wipe_memory(ports_cfg(), out=out.append) == 0, out
    assert 'not running' in out[-1] and 'Backup:' in out[-1]
    backups = list((checkout / 'memory_f' / 'backups').iterdir())
    assert len(backups) == 1
    assert (backups[0] / 'state.json').is_file()
    assert json.loads((backups[0] / 'brain_context' / 'conversations.json').read_text('utf-8'))['turns']
    assert json.loads((backups[0] / 'reset_receipt.json').read_text('utf-8'))['phase'] == 'complete'
    assert MemoryRuntime(checkout / 'memory_f' / 'live').status()['events'] == 0
    assert json.loads((checkout / 'brain' / 'memories' / 'conversations.json').read_text('utf-8')) == {'turns': []}
    assert not (checkout / 'memory_f' / 'reset_pending_live.json').exists()
    assert UsageMeter(ledger).active_requests() == []


def test_wipe_memory_while_she_runs_goes_through_her_gateway_and_offers_force(checkout):
    cfg, seen = ports_cfg(), []
    gateway = f"http://127.0.0.1:{cfg['chat_port']}"
    busy = {'detail': {'code': 'busy', 'message': 'Amika is busy: she is answering. Wait a few seconds and try again, '
                                                  'or force it (she stops what she is doing).'}}
    with stand_in(cfg['brain_port'], {'/api/evo/health': {'app': 'OpenAmika'}}, seen), \
            stand_in(cfg['chat_port'], {'/health': {'app': 'OpenAmika'},
                                        ('POST', '/api/build_f/wipe'): [(409, busy), (200, {'ok': True, 'backup_id': 'b-1'})]},
                     seen):
        out = []
        assert launch.wipe_memory(cfg, out=out.append) == 2
        assert 'she is answering' in out[-2] and '--force' in out[-1]
        assert launch.wipe_memory(cfg, force=True, out=out.append) == 0
        assert out[-1].startswith('Memory wiped. Backup: ') and out[-1].endswith('b-1')
    assert [s[2] for s in seen] == [{'confirmation': 'WIPE', 'wait_s': launch.WIPE_WAIT_S},
                                    {'confirmation': 'WIPE', 'force': True}]
    headers = seen[0][1]
    assert headers['Origin'] == gateway and headers['X-Build-F-Action'] == 'wipe-memory'
    assert MemoryRuntime(checkout / 'memory_f' / 'live').status()['events'] == 1   # the stand-in did the wipe


def test_wipe_memory_refuses_a_port_holder_that_is_not_her_brain(checkout):
    cfg = ports_cfg()
    with stand_in(cfg['brain_port'], {}, []):
        out = []
        assert launch.wipe_memory(cfg, out=out.append) == 1
    assert 'does not answer like her brain' in out[-1]
    assert MemoryRuntime(checkout / 'memory_f' / 'live').status()['events'] == 1


def test_diagnose_zip_has_the_report_log_tails_and_no_secret(checkout):
    (checkout / 'brain' / '.env').write_text(f'OPENROUTER_API_KEY={FAKE_KEY}\n', 'utf-8')
    cfg = example_cfg(checkout)
    cfg['hf_token'] = 'hf_' + 'a' * 30
    (checkout / 'settings.json').write_text(json.dumps(cfg), 'utf-8')
    logs = checkout / 'logs'
    logs.mkdir()
    (logs / 'brain.log').write_text('\n'.join([f'line {i}' for i in range(300)]
                                              + [f'POST failed with key {FAKE_KEY}', 'Authorization: Bearer abcdefgh12345678']),
                                    'utf-8')
    (logs / 'preflight.json').write_text(json.dumps({'at': 'x', 'checks': [], 'summary': {}}), 'utf-8')
    services, held, agents = launch.start_plan(cfg, None)
    path = launch.diagnose(cfg, None, None, None, None, services, agents, held, out=lambda *a: None)
    assert path.parent == logs and path.suffix == '.zip'
    with zipfile.ZipFile(path) as bundle:
        names = set(bundle.namelist())
        assert {'README.txt', 'preflight-now.json', 'preflight-last-start.json', 'logs/brain.log', 'settings.json',
                'system.txt'} <= names
        assert not any(name.endswith('.env') for name in names)
        everything = ''.join(bundle.read(name).decode('utf-8') for name in names)
        brain_log = bundle.read('logs/brain.log').decode('utf-8').splitlines()
        settings = json.loads(bundle.read('settings.json'))
        report = json.loads(bundle.read('preflight-now.json'))
        system = bundle.read('system.txt').decode('utf-8')
    assert FAKE_KEY not in everything and 'abcdefgh12345678' not in everything and 'hf_aaaa' not in everything
    assert len(brain_log) == 200 and brain_log[-1].endswith('<removed>')
    assert settings['hf_token'] == '<removed>' and settings['brain_port'] == cfg['brain_port']
    assert any(c['name'] == 'brain python' for c in report['checks'])
    assert 'RTX Test 8GB' in system and 'disk:' in system and 'launcher python' in system


def test_diagnose_works_before_the_setup_made_settings_json(checkout):
    path = launch.diagnose(None, out=lambda *a: None)
    with zipfile.ZipFile(path) as bundle:
        assert 'settings.json not found' in bundle.read('preflight-now.json').decode('utf-8')


def brain(state='failed'):
    svc = launch.Service('brain', ['python', 'brain/webui.py'], kind='core', port=5202)
    svc.state, svc.detail = state, 'exited with code 1 — see logs/brain.log'
    return svc


def write_log(checkout, *errors):
    logs = checkout / 'logs'
    logs.mkdir(exist_ok=True)
    text = ['--- 2026-11-08 10:00:00 OpenAmika starting brain: python brain/webui.py',
            "ModuleNotFoundError: No module named 'old_problem'"]
    text += ['--- 2026-11-09 12:00:00 OpenAmika starting brain: python brain/webui.py', 'Traceback (most recent call last):',
             *errors]
    (logs / 'brain.log').write_text('\n'.join(text) + '\n', 'utf-8')


@pytest.mark.parametrize('error, why', [
    ("OSError: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 5202)", 'the port is taken'),
    ("ModuleNotFoundError: No module named 'flask_socketio'",
     'the environment is broken: the Python module flask_socketio is missing'),
    ("RuntimeError: Ollama answered HTTP 500: model requires more system memory (19.2 GiB) than is available (7.1 GiB)",
     'the model does not fit in memory'),
    ('ValueError: A key and both mandatory metering callbacks are required', 'the key is missing'),
    ('SystemExit: something nobody foresaw', 'its log ends with: SystemExit: something nobody foresaw'),
])
def test_the_brain_row_says_why_it_did_not_start(checkout, error, why):
    write_log(checkout, error)
    svc = brain()
    svc.why = launch.start_failure(svc)
    assert svc.why.startswith(why), svc.why
    marker, level, desc = svc.light(0)
    assert level == 'err' and why in desc
    report = launch.Report()
    report.core_states([svc])
    assert report.checks == [{'level': 'err', 'name': 'brain start', 'detail': svc.why}]
    svc.state = 'up'
    report.core_states([svc])
    assert report.checks == []


def test_the_preflight_verdict_comes_first(checkout):
    write_log(checkout, "ModuleNotFoundError: No module named 'flask'")
    report = launch.Report()
    report.add('err', 'brain port', '5202 is in use by pid 4242 (python.exe) — that component cannot start')
    assert launch.start_failure(brain(), report) == ('the port is taken: 5202 is in use by pid 4242 (python.exe) — '
                                                    'that component cannot start')


def test_an_up_brain_that_cannot_answer_says_so(checkout):
    svc = brain('up')
    svc.caveat = launch.brain_caveat(launch.Report())
    assert svc.caveat.startswith('the key is missing')
    assert svc.light(0)[1] == 'warn' and 'she cannot answer' in svc.light(0)[2]
    (checkout / 'brain' / '.env').write_text(f'OPENROUTER_API_KEY={FAKE_KEY}\n', 'utf-8')
    assert launch.brain_caveat(launch.Report()) == ''


def ollama_roles(checkout, size_gb, base='http://127.0.0.1:11434'):
    picks = {role: f'{role}:ollama:gemma3:27b' for role in ('surface', 'deep', 'reflection', 'memory_write')}
    (checkout / 'config' / 'llm_roles.json').write_text(json.dumps({'selections': picks}), 'utf-8')
    (checkout / 'config' / 'ollama.json').write_text(json.dumps({'base_url': base, 'models': [
        {'name': 'gemma3:27b', 'size_gb': size_gb}]}), 'utf-8')


def test_a_local_model_that_does_not_fit_the_gpu_is_named(checkout):
    ollama_roles(checkout, 17.4)
    level, detail = launch.model_fit_check(False)
    assert level == 'warn' and 'does not fit' in detail and '8 GB GPU' in detail
    level, _ = launch.model_fit_check(False, gpus=[{'total_mb': 32607}])
    assert level == 'ok'
    report = launch.Report()
    report.add('warn', 'local model fit', detail)
    assert launch.brain_caveat(report).startswith('the model does not fit')
    ollama_roles(checkout, 17.4, base='http://192.168.1.20:11434')     # Ollama on another PC: not this GPU
    assert launch.model_fit_check(False) is None
