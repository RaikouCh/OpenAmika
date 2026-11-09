"""The memory wipe and the model switch are never refused by work that cannot finish (2026-11-09, items 49 and 32).

"Users trying to wipe hit a 'she is busy' error": a request a crashed brain had begun stayed 'started' in the usage
ledger; nothing retired it until 15 minutes had passed (and the model switch never retired it at all), so the wipe
answered 409 "Amika is busy" and the switch "Model selection is busy" — across restarts. Here a turn crashes for
real (a separate process begins a model call and dies), then the wipe and the switch are asked for. Also: one short
wait for a request that is finishing, the forced wipe (she stops what she is doing; the backup is kept; a memory write
or a reflection still in flight brings nothing back), Unlock for the switch, and an orphaned memory job that used to
spin the memory writer. Offline: fake app and providers, temporary stores only.
"""
import contextlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BRAIN = ROOT / 'brain'
sys.path.insert(0, str(BRAIN))
import f_bridge
import f_reset
from f_controls import install_controls
from f_memory import MemoryRuntime
from f_openrouter import OpenRouterClient, abort_streams
from f_roles import NATIVE_KEYS, ROLES, ModelSelectionBusy, install_roles
from f_usage import UsageMeter
import test_f_bridge
from test_f_bridge import FakeApp, FakeSocket, InlineThread

CRASH = '''
import os, sys
sys.path.insert(0, sys.argv[1])
from f_usage import UsageMeter
UsageMeter(sys.argv[2]).begin(sys.argv[3], sys.argv[4], sys.argv[5], 'crashed-turn')
os._exit(3)    # the brain dies mid-turn: nothing ever finishes this request
'''


def crash_mid_turn(ledger, provider='anthropic', model='claude-sonnet-5', phase='deep'):
    """A brain process that begins a model call and dies before it finishes (a crash, a kill, a quick restart)."""
    done = subprocess.run([sys.executable, '-B', '-c', CRASH, str(BRAIN), str(ledger), provider, model, phase],
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 3, done.stderr


class Request:
    method = 'POST'
    is_json = True

    def __init__(self, value=None, action='wipe-memory'):
        self.headers = {'X-Build-F-Action': action}
        self.value = {'confirmation': 'WIPE'} if value is None else value

    def get_json(self, **kwargs):
        return self.value


class WipeFixture(unittest.TestCase):
    """The real bridge (f_bridge.install: memory, ledger, reset, controls) with old memories and a transcript."""

    def setUp(self):
        self.fixture = test_f_bridge.BridgeTests()
        self.fixture.setUp()
        self.extra = []
        self.prepare(self.fixture.g)
        self.fixture.install()
        self.g, self.root = self.fixture.g, self.fixture.root
        self.memory, self.meter = self.g['F_MEMORY'], self.g['F_METER']
        context = self.root / 'brain' / 'memories'
        context.mkdir()
        for name in ('conversations.json', 'thinking_log.json', 'consolidated.json'):
            (context / name).write_text(json.dumps({'old': 'Private old context'}), encoding='utf-8')
        self.g['CONVERSATION_HISTORY'].append({'turn_id': 'old', 'user': 'Old message'})
        self.memory.archive({'id': 'old-event', 'time': '2026-09-26T01:00:00Z', 'user': 'I like blue.',
                             'assistant': 'Okay.', 'source_kind': 'conversation'})
        self.wipe = self.g['app'].view_functions['/api/build_f/wipe']

    def prepare(self, g):
        """Hook for subclasses: change the fake brain before f_bridge installs on it."""

    def tearDown(self):
        for other in self.extra:
            other.tearDown()
        self.fixture.tearDown()

    def route(self, value=None):
        self.g['request'] = Request(value)
        return self.wipe()

    def restart(self):
        """A new brain on the same folder (f_bridge.install again): what a restart of OpenAmika does."""
        again = test_f_bridge.BridgeTests()
        again.setUp()
        self.extra.append(again)
        again.g['__file__'] = self.g['__file__']
        f_bridge.install(again.g)
        return again.g


class CrashedTurnTests(WipeFixture):
    def test_a_request_from_a_crashed_brain_never_blocks_the_wipe(self):
        crash_mid_turn(self.root / 'memory_f' / 'usage.sqlite')
        self.assertEqual(len(self.meter.active_requests()), 1)
        result, code = self.route()
        self.assertEqual(code, 200, result)
        backup = self.root / 'memory_f' / 'backups' / result['backup_id']
        self.assertTrue((backup / 'state.json').exists())
        self.assertEqual(json.loads((backup / 'brain_context' / 'conversations.json').read_text())['old'],
                         'Private old context')
        self.assertEqual(self.memory.status()['events'], 0)
        self.assertEqual(self.meter.active_requests(), [])
        row = next(r for r in self.meter.summary()['recent_requests'] if r['turn_id'] == 'crashed-turn')
        self.assertEqual(row['status'], 'unknown')

    def test_a_restart_right_after_the_crash_clears_it_whatever_its_age(self):
        crash_mid_turn(self.root / 'memory_f' / 'usage.sqlite')
        g = self.restart()                      # seconds later: the old boot sweep only took rows older than 15 min
        self.assertEqual(g['F_METER'].active_requests(), [])
        g['request'] = Request()
        result, code = g['app'].view_functions['/api/build_f/wipe']()
        self.assertEqual(code, 200, result)

    def test_a_turn_thread_that_died_between_begin_and_finish(self):
        def crashed_turn():
            self.meter.begin('anthropic', 'claude-sonnet-5', 'deep', 'dead-thread', estimated_max_usd=.01)
            raise RuntimeError('the turn died before finishing its request')
        with patch.object(threading, 'excepthook', lambda args: None):
            thread = threading.Thread(target=crashed_turn)
            thread.start()
            thread.join(5)
        # within the grace a drain thread could still own it; after it, it is retired like any dead request
        self.assertEqual(self.route()[1], 409)
        self.meter.LEAK_GRACE_S = 0
        result, code = self.route()
        self.assertEqual(code, 200, result)

    def test_the_wipe_waits_once_for_her_to_finish(self):
        ident = self.meter.begin('anthropic', 'claude-sonnet-5', 'deep', 'answering', estimated_max_usd=.01)
        result, code = self.route()
        self.assertEqual(code, 409)
        self.assertEqual(result['code'], 'busy')
        self.assertIn('her answer (claude-sonnet-5', result['error'])
        self.assertIn('force', result['error'])
        timer = threading.Timer(0.4, lambda: self.meter.finish(ident, {'input_tokens': 5, 'output_tokens': 1}))
        timer.start()
        started = time.monotonic()
        result, code = self.route({'confirmation': 'WIPE', 'wait_s': 8})
        timer.join()
        self.assertEqual(code, 200, result)
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(self.memory.status()['events'], 0)

    def test_bad_force_or_wait_values_are_refused(self):
        for value in ({'confirmation': 'WIPE', 'force': 'yes'}, {'confirmation': 'WIPE', 'wait_s': 99},
                      {'confirmation': 'WIPE', 'wait_s': True}):
            self.assertEqual(self.route(value)[1], 400, value)
        self.assertEqual(self.memory.status()['events'], 1)

    def test_force_stops_her_and_still_keeps_the_backup(self):
        cancel = threading.Event()
        self.g['_ws_active']['turn-live'] = {'cancel': cancel, 'reason': None}
        ident = self.meter.begin('anthropic', 'claude-sonnet-5', 'deep', 'turn-live', estimated_max_usd=.01)
        self.assertEqual(self.route()[1], 409)
        with patch.object(f_reset, 'FORCE_SETTLE_S', 0.2):
            result, code = self.route({'confirmation': 'WIPE', 'force': True})
        self.assertEqual(code, 200, result)
        self.assertTrue(result['forced'])
        self.assertTrue(cancel.is_set())
        self.assertEqual(self.g['_ws_active']['turn-live']['reason'], 'discard')
        self.assertEqual(result['stopped']['turns'], 1)
        self.assertEqual(result['retired_requests'], 1)
        backup = self.root / 'memory_f' / 'backups' / result['backup_id']
        self.assertTrue((backup / 'state.json').exists() and (backup / 'brain_context' / 'conversations.json').exists())
        self.assertEqual(self.memory.status()['events'], 0)
        self.assertEqual(self.g['CONVERSATION_HISTORY'], [])
        # the call she was making when she was stopped still records what it used once it returns
        receipt = self.meter.finish(ident, {'input_tokens': 40, 'output_tokens': 4})
        self.assertEqual(receipt['tokens']['output_tokens'], 4)

    def test_force_fences_off_a_memory_write_still_waiting_on_its_model(self):
        entered, release = threading.Event(), threading.Event()
        extract = self.memory.extract_fn

        def slow_local_model(events, chunk):
            entered.set()
            release.wait(10)
            return extract(events, chunk)
        self.memory.extract_fn = slow_local_model
        writer = threading.Thread(target=self.memory.flush_pending)
        writer.start()
        try:
            self.assertTrue(entered.wait(5))
            result, code = self.route()
            self.assertEqual(code, 409)
            self.assertIn('memory writer', result['error'])
            with patch.object(f_reset, 'FORCE_SETTLE_S', 0.2):
                result, code = self.route({'confirmation': 'WIPE', 'force': True})
            self.assertEqual(code, 200, result)
        finally:
            release.set()
            writer.join(10)
        # what the writer brought back after the wipe went nowhere: the new store stays empty
        status = self.memory.status()
        self.assertEqual((status['events'], status['facts'], status['pending']), (0, 0, 0))
        self.assertEqual(list(self.memory.jobs_dir.glob('*.json')), [])
        backup = self.root / 'memory_f' / 'backups' / result['backup_id']
        self.assertEqual(len(list((backup / 'jobs').glob('*.json'))), 1)

    def test_an_orphaned_memory_job_neither_spins_the_writer_nor_blocks_the_wipe(self):
        path = next(self.memory.jobs_dir.glob('*.json'))
        job = json.loads(path.read_text(encoding='utf-8'))
        job['state'] = 'extracting'             # its worker ended mid-dispatch without recording an outcome
        path.write_text(json.dumps(job), encoding='utf-8')
        self.assertEqual(self.memory.status()['pending'], 1)
        with patch.object(f_bridge.threading, 'Thread', InlineThread):
            self.g['f_memory_flush']()          # returns: it used to loop forever holding the worker lock
        self.assertEqual(self.memory.status()['pending'], 0)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['state'], 'retry_wait')
        self.assertEqual(self.route()[1], 200)


class StoppedReflectionTests(WipeFixture):
    """A reflection that Unlock or a forced wipe stopped (or one that began before a wipe) brings nothing back."""

    def prepare(self, g):
        self.logged, self.opened = [], []
        self.streaming, self.release = threading.Event(), threading.Event()
        g['parse_thinking_response'] = lambda raw: {'开口': 'You are quiet today.'}
        g['add_thinking_entry'] = self.logged.append
        g['_maybe_fire_open'] = lambda content: self.opened.append(content) or 'open-1'

        def thinking(deep_request='', on_guidance=None, target_turn_id=None):
            self.streaming.set()
            self.release.wait(5)
            parsed = g['parse_thinking_response']('raw')
            g['add_thinking_entry']({'raw': 'raw'})
            g['_maybe_fire_open'](parsed['开口'])
            return parsed
        g['run_thinking_once'] = thinking

    def reflect(self):
        outcome = {}

        def run():
            try:
                outcome['result'] = self.g['run_thinking_once']('idle')
            except Exception as error:
                outcome['error'] = error
        thread = threading.Thread(target=run)
        thread.start()
        self.assertTrue(self.streaming.wait(5))
        return thread, outcome

    def test_a_reflection_runs_as_before(self):
        self.release.set()
        thread, outcome = self.reflect()
        thread.join(5)
        self.assertNotIn('error', outcome)
        self.assertEqual((len(self.logged), self.opened), (1, ['You are quiet today.']))

    def test_unlock_stops_a_running_reflection_and_drops_its_result(self):
        thread, outcome = self.reflect()
        self.assertEqual(self.g['F_STOP_WORK']()['reflections'], 1)
        self.release.set()
        thread.join(5)
        self.assertIn('stopped', str(outcome.get('error')))
        self.assertEqual((self.logged, self.opened), ([], []))

    def test_a_reflection_from_before_a_wipe_drops_its_result(self):
        thread, outcome = self.reflect()
        self.g['F_WORK_EPOCH'][0] += 1          # a wipe happened meanwhile
        self.release.set()
        thread.join(5)
        self.assertEqual((self.logged, self.opened), ([], []))


class HTTP:
    def __init__(self):
        self.responses, self.calls = [], []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class ModelSwitchTests(unittest.TestCase):
    """Item 32: the model switch after a model crashed mid-turn — the lock no longer survives a restart, and Unlock
    gets past a model that still hangs."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / 'config').mkdir()
        shutil.copyfile(ROOT / 'config' / 'openrouter_models.json', self.root / 'config' / 'openrouter_models.json')
        document = {'version': 1, 'options': {}, 'selections': {}}
        for role in ROLES:
            document['options'][role] = [
                {'key': 'native:' + NATIVE_KEYS[role], 'native_key': NATIVE_KEYS[role], 'name': 'Native'},
                {'key': 'or:' + role, 'model_id': 'deepseek/deepseek-v4-flash-0731', 'name': 'Reviewed ' + role}]
            document['selections'][role] = 'or:' + role
        (self.root / 'config' / 'llm_roles.json').write_text(json.dumps(document), encoding='utf-8')
        self.ledger = self.root / 'memory_f' / 'usage.sqlite'
        self.memories = []
        self.stopped = []
        self.boot()

    def boot(self):
        """The brain's start: a meter on the ledger with f_bridge's boot sweep, the role manager, the controls."""
        memory = MemoryRuntime(self.root / 'memory_f' / 'live', lambda events, chunk: {'facts': []},
                               lambda texts, task: [[1.] + [0.] * 767 for t in texts])
        self.memories.append(memory)
        self.meter = UsageMeter(self.ledger, {'models': {}})
        self.meter.retire_dead()
        self.g = {'AVAILABLE_MODELS': {key: {'name': key, 'provider': 'native', 'model': key} for key in NATIVE_KEYS.values()},
                  '_ws_active_lock': threading.RLock(), '_ws_active': {}, '_thinking_inflight': 0,
                  'http_requests': HTTP(), 'OPENROUTER_KEY': 'fake-key',
                  '_pick_stream': lambda p, c, **kw: iter(['native']),
                  '_openai_messages': lambda p, **kw: [{'role': 'user', 'content': p.get('user_content', '')}],
                  'app': FakeApp(), 'socketio': FakeSocket(), 'jsonify': lambda value: value, 'F_MEMORY': memory,
                  'F_STOP_WORK': lambda reason='interrupt': self.stopped.append(reason) or {'turns': 0}}

        @contextlib.contextmanager
        def scope(phase, turn_id='', **kwargs):
            yield
        self.manager = install_roles(self.g, self.root, memory, self.meter, scope, threading.local(), {})
        install_controls(self.g, self.meter)
        self.models = self.g['app'].view_functions['/api/build_f/models']
        self.unlock = self.g['app'].view_functions['/api/build_f/unlock']

    def tearDown(self):
        for memory in self.memories:
            memory.close()
        self.tmp.cleanup()

    def native(self):
        return {role: 'native:' + NATIVE_KEYS[role] for role in ROLES}

    def post(self, view, value, action):
        self.g['request'] = Request(value, action)
        return view()

    def test_a_crashed_model_call_no_longer_locks_the_switch(self):
        crash_mid_turn(self.ledger, 'openrouter', 'deepseek/deepseek-v4-flash-0731')
        result = self.post(self.models, {'selections': self.native()}, 'select-models')
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.manager.get()['selections'], self.native())

    def test_crash_mid_turn_restart_then_switch(self):
        crash_mid_turn(self.ledger, 'openrouter', 'deepseek/deepseek-v4-flash-0731')
        self.boot()                              # the restart, seconds after the crash
        self.assertEqual(self.meter.active_requests(), [])
        self.assertEqual(self.manager.set(self.native())['selections'], self.native())

    def test_unlock_then_a_forced_switch_gets_past_a_model_that_still_hangs(self):
        release = threading.Event()
        begun = threading.Event()

        def hung_model_call():
            ident = self.meter.begin('openrouter', 'deepseek/deepseek-v4-flash-0731', 'deep', 'hung-turn')
            begun.set()
            release.wait(10)
            self.meter.finish(ident, {'prompt_tokens': 10, 'completion_tokens': 2, 'cost': 0.0})
        thread = threading.Thread(target=hung_model_call)
        thread.start()
        try:
            self.assertTrue(begun.wait(5))
            result, code = self.post(self.models, {'selections': self.native()}, 'select-models')
            self.assertEqual(code, 409)
            self.assertEqual(result['code'], 'model_busy')
            self.assertIn('a model call is in flight', result['busy'])
            unlocked = self.post(self.unlock, {}, 'unlock')
            self.assertTrue(unlocked['ok'])
            self.assertEqual(self.stopped, ['interrupt'])           # she stops what she is doing
            result = self.post(self.models, {'selections': self.native(), 'force': True}, 'select-models')
            self.assertTrue(result['ok'], result)
            self.assertEqual(json.loads((self.root / 'config' / 'llm_roles.json').read_text())['selections'],
                             self.native())
        finally:
            release.set()
            thread.join(5)
        self.assertEqual(self.meter.active_requests(), [])

    def test_unlock_recovers_an_orphaned_memory_job(self):
        memory = self.g['F_MEMORY']
        memory.archive({'id': 'e1', 'time': '2026-09-26T01:00:00Z', 'user': 'Hi.', 'assistant': 'Hello.',
                        'source_kind': 'conversation'})
        path = next(memory.jobs_dir.glob('*.json'))
        job = json.loads(path.read_text(encoding='utf-8'))
        job['state'] = 'embedding'
        path.write_text(json.dumps(job), encoding='utf-8')
        with self.assertRaises(ModelSelectionBusy):
            self.manager.set(self.native())
        self.assertEqual(self.post(self.unlock, {'stop': False}, 'unlock')['recovered_jobs'], 1)
        self.assertEqual(self.stopped, [])
        self.assertEqual(self.manager.set(self.native())['selections'], self.native())

    def test_unlock_refuses_bad_requests(self):
        self.assertEqual(self.post(self.unlock, {'stop': 'yes'}, 'unlock')[1], 400)
        self.assertEqual(self.post(self.unlock, {'everything': True}, 'unlock')[1], 400)
        self.g['request'] = Request({}, 'unlock')
        self.g['request'].headers['Origin'] = 'https://elsewhere.invalid'
        self.assertEqual(self.unlock()[1], 403)


class HungStream:
    """A model stream that sends one line and then hangs until it is closed (a local model that crashed mid-answer)."""

    def __init__(self):
        self.closed = threading.Event()

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        yield 'data: ' + json.dumps({'id': 'gen-1', 'choices': [{'delta': {'content': 'Hel'}}]})
        self.closed.wait(10)
        raise ConnectionError('the response was closed')

    def close(self):
        self.closed.set()


class AbortStreamsTests(unittest.TestCase):
    def test_stop_work_closes_a_hung_stream_and_its_request_is_settled(self):
        receipts = []
        stream = HungStream()
        client = OpenRouterClient(type('H', (), {'post': lambda self, url, **kw: stream})(), 'fake-not-a-key',
                                  lambda request: 'handle-1', lambda handle, receipt: receipts.append(receipt))
        from f_openrouter import load_catalog, role_config
        config = role_config(load_catalog(ROOT / 'config' / 'openrouter_models.json'),
                             'deepseek/deepseek-v4-flash-0731', 'deep')
        outcome = {}

        def read():
            try:
                outcome['text'] = ''.join(client.stream(config, [{'role': 'user', 'content': 'Hi'}]))
            except Exception as error:
                outcome['error'] = error
        thread = threading.Thread(target=read)
        thread.start()
        deadline = time.monotonic() + 5
        while abort_streams() == 0 and time.monotonic() < deadline:
            time.sleep(0.05)
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertIn('error', outcome)
        self.assertEqual(len(receipts), 1)                  # settled exactly once: the ledger row does not stay open
        self.assertEqual(abort_streams(), 0)


if __name__ == '__main__':
    unittest.main()
