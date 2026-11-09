"""Exercise reset routing offline; no model/STT imports and no live reset calls."""
import ast
import asyncio
import base64
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'payload' / 'api.py'
if not SOURCE.exists():
    SOURCE = Path(__file__).resolve().parents[1] / 'speech' / 'api.py'   # repo layout


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Request:
    def __init__(self, origin='https://example.test:8445', body=None, headers=None):
        self.url = SimpleNamespace(scheme='https', netloc='example.test:8445')
        self.headers = {'origin': origin, 'content-type': 'application/json', 'x-build-f-action': 'wipe-memory'}
        self.headers.update(headers or {})
        self.data = json.dumps({'confirmation': 'WIPE'}).encode() if body is None else body

    async def body(self):
        return self.data


class Response:
    def __init__(self, status=200, data=None):
        self.status = status
        self.data = {'ok': True, 'backup_id': 'backup-1', 'memory': {'events': 0}, 'usage': {'total_requests': 5}} if data is None else data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def json(self):
        return self.data


class FakeHTTP:
    class ClientError(Exception):
        pass

    def __init__(self):
        self.calls = []
        self.response = Response()
        self.on_post = None

    def ClientTimeout(self, **kwargs):
        return kwargs

    def ClientSession(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def post(self, url, **kwargs):
        if self.on_post:
            self.on_post()
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class Connection:
    def __init__(self):
        self.disconnected = False

    async def disconnect(self):
        self.disconnected = True


class Socket:
    def __init__(self):
        self.closed = False
        self.messages = []

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.closed = True

    async def send_json(self, data):
        self.messages.append(data)


class Session:
    def __init__(self):
        self._connecting = False
        self._input_busy = False
        self._wipe_retired = False
        self._pending_partial = None
        self._state = 'IDLE'
        self._committed_turn_id = None
        self._current_sent_id = None
        self._ai_end_received = False  # A fresh connection is idle despite this default.
        self._tts_playing = None
        self._tts_inflight = None
        self._tts_sentence_queue = []
        self._tts_pending_play = set()
        self._pending_context = 'private context'
        self._context_revision = 2
        self._contexts_sent = {'old-turn': (2, 'private context')}
        self._pending_chunks = ['old chunk']
        self._buffered_proactive = {'old-turn': []}
        self._leftover = bytearray(b'old pcm')
        self._speech_frames = ['old audio']
        # STT carry state (added to api.py on 2026-09-26; the retire path clears it)
        self._carry_text = 'carried words'
        self._last_commit_text = 'last'
        self._carry_turn_ids = {'old-turn'}
        self._carry_error_turns = {'err-turn'}
        self._carry_snapshot = ('old-turn', 'carried words')
        self._protect_inflight = 'old-turn'
        self.events = []
        self.hane, self.tts, self.ws = Connection(), Connection(), Socket()

    def _reset_utterance(self):
        self._speech_frames = []

    def _reset_tts_for_new_turn(self):
        self._tts_pending_play.clear()

    def _surface_last_item(self, kind):     # DialogSession's: is this the surface's final audio (none queued here)
        return False

    async def _send(self, event):
        self.events.append(event)


class WipeProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.ns = {'asyncio': asyncio, 'json': json, 'aiohttp': self.http, 'Request': Request,
                   'HTTPException': HTTPException, 'WebSocket': Socket, '_dialog_sessions': set(),
                   '_wipe_in_progress': False, '_dialog_active': False, 'HANE_URL': 'http://127.0.0.1:5201',
                   'vision_note_her_speech': lambda s: None}   # vision hook in the audio receipt path
        self.tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        wanted = {'_build_f_session_busy', '_retire_wiped_sessions', 'build_f_wipe', 'ws_dialog',
                  '_reset_options', '_wait_sessions_idle', '_brain_refusal', 'build_f_reset'}
        nodes = [copy.deepcopy(n) for n in self.tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in wanted]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(nodes, type_ignores=[]), '<wipe proxy>', 'exec'), self.ns)

    async def assert_refused(self, request, status):
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_wipe'](request)
        self.assertEqual(caught.exception.status_code, status)
        self.assertFalse(self.ns['_wipe_in_progress'])
        return caught.exception

    async def test_origin_confirmation_contenttype_and_action_fail_closed(self):
        cases = [(Request(origin=None), 403), (Request(origin='https://other.test'), 403),
                 (Request(origin='http://example.test:8445'), 403), (Request(origin='https://example.test'), 403),
                 (Request(headers={'x-build-f-action': ''}), 403), (Request(headers={'content-type': 'text/plain'}), 415),
                 (Request(body=b'{'), 400), (Request(body=b'{"confirmation":"wipe"}'), 400),
                 (Request(body=b'[]'), 400), (Request(body=b'x' * 1025), 400)]
        for request, status in cases:
            with self.subTest(status=status, headers=request.headers):
                await self.assert_refused(request, status)
        self.assertEqual(self.http.calls, [])

    async def test_raw_forwarded_headers_cannot_change_origin_trust(self):
        await self.assert_refused(Request(origin='https://evil.test', headers={'x-forwarded-host': 'evil.test', 'x-forwarded-proto': 'https'}), 403)
        self.assertEqual(self.http.calls, [])

    async def test_busy_audio_generation_asr_and_connecting_refuse_without_disconnect(self):
        variations = [('_state', 'SPEAKING'), ('_state', 'SHORT_PAUSE'), ('_connecting', True), ('_input_busy', True),
                      ('_tts_playing', {'idx': 0}), ('_tts_inflight', {'idx': 0}), ('_tts_sentence_queue', ['audio']),
                      ('_tts_pending_play', {0}), ('_committed_turn_id', 'generating'),
                      ('_pending_partial', SimpleNamespace(done=lambda: False))]
        for key, value in variations:
            with self.subTest(key=key):
                session = Session()
                setattr(session, key, value)
                self.ns['_dialog_sessions'] = {session}
                await self.assert_refused(Request(), 409)
                self.assertEqual(session._pending_context, 'private context')
                self.assertFalse(session.ws.closed)
        self.assertEqual(self.http.calls, [])

    async def test_success_calls_only_fixed_endpoint_clears_all_sessions_and_keeps_usage(self):
        sessions = [Session(), Session()]
        self.ns['_dialog_sessions'].update(sessions)
        self.http.on_post = lambda: self.assertTrue(self.ns['_wipe_in_progress'])
        result = await self.ns['build_f_wipe'](Request())
        self.assertTrue(result['ok'])
        self.assertEqual(result['usage']['total_requests'], 5)
        self.assertEqual(self.http.calls, [('http://127.0.0.1:5201/api/build_f/wipe', {
            'json': {'confirmation': 'WIPE'}, 'headers': {'X-Build-F-Action': 'wipe-memory'}, 'allow_redirects': False})])
        for session in sessions:
            self.assertTrue(session.hane.disconnected and session.tts.disconnected and session.ws.closed)
            self.assertEqual(session._pending_context, '')
            self.assertEqual(session._contexts_sent, {})
            self.assertEqual(session._speech_frames, [])
            self.assertTrue(session._wipe_retired)
            self.assertEqual(session.events[0], {'type': 'memory_wiped', 'backup_id': 'backup-1'})
        self.assertFalse(self.ns['_wipe_in_progress'])

    async def test_brain_busy_keeps_context_and_connection(self):
        session = Session()
        self.ns['_dialog_sessions'].add(session)
        self.http.response = Response(status=409)
        await self.assert_refused(Request(), 409)
        self.assertFalse(session.ws.closed)
        self.assertEqual(session._pending_context, 'private context')
        self.assertEqual(session.events, [])

    async def test_uncertain_outcome_disconnects_stale_context_without_success_clear_event(self):
        for response in [Response(status=503), Response(data={'ok': False}), self.http.ClientError('connection lost')]:
            session = Session()
            self.ns['_dialog_sessions'] = {session}
            self.http.response = response
            await self.assert_refused(Request(), 503)
            self.assertTrue(session.ws.closed)
            self.assertEqual(session._pending_context, '')
            self.assertEqual(session.events[0]['type'], 'memory_reset_uncertain')

    async def test_new_dialog_is_refused_during_reset(self):
        self.ns['_wipe_in_progress'] = True
        socket = Socket()
        await self.ns['ws_dialog'](socket)
        self.assertTrue(socket.closed)
        self.assertIn('service control is in progress', socket.messages[0]['message'])

    async def test_ordinary_audio_marked_pending_before_the_browser_gets_it(self):
        cls = next(n for n in self.tree.body if isinstance(n, ast.ClassDef) and n.name == 'DialogSession')
        method = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == '_on_tts_event'))
        self.ns.update(base64=base64, _now_ms=lambda: 1, pause_after=lambda *a: 0,
                       logger=SimpleNamespace(info=lambda *a: None, debug=lambda *a: None, warning=lambda *a: None))
        exec(compile(ast.Module([method], type_ignores=[]), '<audio receipt>', 'exec'), self.ns)
        session = Session()
        session._committed_turn_id = 'turn'
        session._tts_inflight = {'task_id': 'task', 'idx': 0, 'sentence': 'hello', 'sent_ms': 0}
        session._tts_sentences_by_idx = {}
        session._tts_first_audio_sent = True
        session._peer = 'test'
        session._detect_lang = lambda text: 'ENGLISH'
        async def send(event):
            self.assertEqual(session._tts_pending_play, {0})
            self.assertIn(0, session._tts_sentences_by_idx)
            self.assertTrue(self.ns['_build_f_session_busy'](session))
        async def pump():
            pass
        session._send, session._pump_tts_queue = send, pump
        await self.ns['_on_tts_event'](session, 'audio_ready', {'task_id': 'task', 'turn_id': 'turn-0',
                                                             'audio': b'RIFFsample', 'audio_duration': 1.0, 'audio_format': 'wav'})


if __name__ == '__main__':
    unittest.main()
