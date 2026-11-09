"""The gateway side of the wipe that never stays "busy" (2026-11-09, items 49 and 32), offline: speech/api.py's
functions lifted out by AST, a fake brain behind HANE_URL.

- The wipe and the full reset wait once (wait_s) for the stage to go idle, take force (busy sessions no longer refuse
  it; the sessions are retired as after every wipe) and pass the brain's own reasons on as {code, message}.
- A turn the brain was answering when its connection dropped (a crash, a restart) ends on the gateway too, instead of
  keeping the session busy until the page is reloaded.
- Her playback acks still count while a service control runs (dropping one left a clip "playing" forever).
- Unlock stops her on the page too; the model switch after it skips the session check (X-Build-F-Force: 1).
"""
import ast
import asyncio
import copy
import json
import unittest
from types import SimpleNamespace

from test_wipe_proxy import SOURCE, Connection, FakeHTTP, HTTPException, Request, Response, Session, Socket

TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
WANTED = {'_build_f_session_busy', '_retire_wiped_sessions', 'build_f_wipe', 'build_f_reset', 'ws_dialog',
          '_reset_options', '_wait_sessions_idle', '_brain_refusal', '_build_f_control', 'build_f_unlock',
          'build_f_select_models', 'build_f_conversation_get', 'build_f_conversation_set'}


def session_method(name):
    """A DialogSession method, lifted out on its own (to call it on a fake session)."""
    cls = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'DialogSession')
    method = copy.deepcopy(next(n for n in cls.body if isinstance(n, ast.AsyncFunctionDef) and n.name == name))
    space = {}
    exec(compile(ast.Module([method], type_ignores=[]), '<session method>', 'exec'), space)
    return space[name]


class Gateway(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.http.get = self.http.post
        self.ns = {'asyncio': asyncio, 'json': json, 'aiohttp': self.http, 'Request': Request,
                   'HTTPException': HTTPException, 'WebSocket': Socket, '_dialog_sessions': set(),
                   '_wipe_in_progress': False, '_dialog_active': False, 'HANE_URL': 'http://127.0.0.1:5201',
                   'WebSocketDisconnect': type('WebSocketDisconnect', (Exception,), {}),
                   'logger': SimpleNamespace(info=lambda *a: None, debug=lambda *a: None, warning=lambda *a: None,
                                             exception=lambda *a: None)}
        nodes = [copy.deepcopy(n) for n in TREE.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in WANTED]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(nodes, type_ignores=[]), '<gateway>', 'exec'), self.ns)

    def wipe_request(self, **body):
        return Request(body=json.dumps({'confirmation': 'WIPE', **body}).encode())


class ForcedWipeTests(Gateway):
    async def test_force_goes_past_a_busy_stage_and_retires_it(self):
        session = Session()
        session._tts_playing = {'idx': 0}          # she is mid-sentence
        self.ns['_dialog_sessions'] = {session}
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_wipe'](self.wipe_request())
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.detail['code'], 'busy')
        self.assertEqual(self.http.calls, [])
        result = await self.ns['build_f_wipe'](self.wipe_request(force=True))
        self.assertTrue(result['ok'])
        self.assertEqual(self.http.calls[0][1]['json'], {'confirmation': 'WIPE', 'force': True})
        self.assertTrue(session._wipe_retired and session.ws.closed)
        self.assertFalse(self.ns['_wipe_in_progress'])

    async def test_one_short_wait_for_the_stage_to_go_idle(self):
        session = Session()
        session._tts_pending_play = {3}            # her last clip is still playing
        self.ns['_dialog_sessions'] = {session}

        async def finishes():
            await asyncio.sleep(0.3)
            session._tts_pending_play.clear()       # tts_finished arrived
        asyncio.create_task(finishes())
        result = await self.ns['build_f_wipe'](self.wipe_request(wait_s=3))
        self.assertTrue(result['ok'])
        self.assertEqual(self.http.calls[0][1]['json'], {'confirmation': 'WIPE', 'wait_s': 3})

    async def test_the_brains_reasons_reach_the_page(self):
        self.http.response = Response(status=409, data={'ok': False, 'code': 'busy',
                                                        'error': 'Amika is busy: she is reflecting. Wait a few seconds.'})
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_wipe'](self.wipe_request())
        self.assertEqual(caught.exception.detail, {'code': 'busy',
                                                   'message': 'Amika is busy: she is reflecting. Wait a few seconds.'})

    async def test_bad_options_are_refused_before_anything_runs(self):
        for body in ({'force': 1}, {'wait_s': 60}, {'wait_s': 'soon'}):
            with self.assertRaises(HTTPException) as caught:
                await self.ns['build_f_wipe'](self.wipe_request(**body))
            self.assertEqual(caught.exception.status_code, 400, body)
            self.assertFalse(self.ns['_wipe_in_progress'])
        self.assertEqual(self.http.calls, [])

    async def test_reset_everything_takes_force_too(self):
        session = Session()
        session._committed_turn_id, session._ai_end_received = 'turn-1', False
        self.ns['_dialog_sessions'] = {session}
        self.http.response = Response(data={'ok': True, 'backup_id': 'b-2', 'restored': [], 'memory': {}, 'usage': {}})
        self.http.response.content_type = 'application/json'
        request = Request(body=json.dumps({'confirmation': 'RESET', 'force': True}).encode(),
                          headers={'x-build-f-action': 'reset-all'})
        result = await self.ns['build_f_reset'](request)
        self.assertEqual(result['backup_id'], 'b-2')
        self.assertEqual(self.http.calls[0][1]['json'], {'confirmation': 'RESET', 'force': True})


class TruthfulSessionTests(Gateway):
    async def test_a_turn_the_brain_never_ended_ends_when_its_connection_drops(self):
        session = Session()
        session._committed_turn_id, session._ai_end_received = 'turn-7', False
        self.assertTrue(self.ns['_build_f_session_busy'](session))
        await session_method('_brain_lost')(session)
        self.assertFalse(self.ns['_build_f_session_busy'](session))
        self.assertEqual([e['type'] for e in session.events], ['ai_error', 'ai_end'])
        await session_method('_brain_lost')(session)           # once only
        self.assertEqual(len(session.events), 2)

    async def test_stop_her_ends_her_turn_and_audio(self):
        session = Session()
        session._committed_turn_id, session._ai_end_received = 'turn-8', False
        session._tts_playing, session._tts_inflight = {'idx': 1}, {'idx': 2}
        session._tts_sentence_queue, session._tts_pending_play = ['next'], {1}
        await session_method('stop_her')(session)
        self.assertFalse(self.ns['_build_f_session_busy'](session))
        self.assertEqual([e['type'] for e in session.events], ['stop_audio', 'ai_end'])

    async def test_playback_acks_still_count_during_a_service_control(self):
        acks, sent, ns = [], [], self.ns

        class Link(Connection):
            _connected = True

            async def connect(self):
                pass

        class FakeDialog:
            SAMPLE_RATE, FRAME_SAMPLES = 16000, 512

            def __init__(self, ws):
                self.ws, self.hane, self.tts = ws, Link(), Link()
                self._pending_partial = None
                ns['_wipe_in_progress'] = True       # a model switch or a wipe is being applied right now

            async def _send(self, event):
                sent.append(event)

            async def on_frontend_tts_finished(self, data):
                acks.append(data)

            async def on_text(self, data):
                raise AssertionError('no input may start a turn during a control')

        class Page(Socket):
            def __init__(self, messages):
                super().__init__()
                self.queue = list(messages)

            async def receive(self):
                if self.queue:
                    return self.queue.pop(0)
                ns['_wipe_in_progress'] = False
                return {'type': 'websocket.disconnect'}
        self.ns['DialogSession'] = FakeDialog
        page = Page([{'type': 'websocket.receive', 'text': json.dumps({'type': 'tts_finished', 'turn_id': 't-0', 'idx': 0})},
                     {'type': 'websocket.receive', 'text': json.dumps({'type': 'text', 'text': 'hi'})}])
        await asyncio.wait_for(self.ns['ws_dialog'](page), 5)
        self.assertEqual(acks, [{'type': 'tts_finished', 'turn_id': 't-0', 'idx': 0}])
        self.assertTrue(any(e.get('type') == 'ai_error' and 'service control' in e.get('message', '') for e in sent))
        self.assertFalse(self.ns['_dialog_active'])


class UnlockProxyTests(Gateway):
    def control(self, action, value, **headers):
        return Request(body=json.dumps(value).encode(), headers={'x-build-f-action': action, **headers})

    async def test_unlock_reaches_the_brain_and_stops_her_on_the_page(self):
        stopped = []
        session = Session()

        async def stop_her():
            stopped.append(True)
        session.stop_her = stop_her
        session._tts_playing = {'idx': 0}                      # a control that does not check busy still runs
        self.ns['_dialog_sessions'] = {session}
        self.http.response = Response(data={'ok': True, 'retired_requests': 2, 'recovered_jobs': 0,
                                            'stopped': {'turns': 1}, 'still_running': [], 'secret': 'no'})
        result = await self.ns['build_f_unlock'](self.control('unlock', {}))
        self.assertEqual(result['retired_requests'], 2)
        self.assertNotIn('secret', result)
        self.assertEqual(self.http.calls[0][0], 'http://127.0.0.1:5201/api/build_f/unlock')
        self.assertEqual(stopped, [True])

    async def test_the_forced_switch_skips_the_stage_check(self):
        session = Session()
        session._state = 'SPEAKING'
        self.ns['_dialog_sessions'] = {session}
        value = {'selections': {'deep': 'x'}, 'force': True}
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_select_models'](self.control('select-models', value))
        self.assertEqual(caught.exception.status_code, 409)
        self.http.response = Response(data={'ok': True, 'selections': {'deep': 'x'}})
        result = await self.ns['build_f_select_models'](self.control('select-models', value, **{'x-build-f-force': '1'}))
        self.assertTrue(result['ok'])
        self.assertEqual(self.http.calls[0][1]['json'], value)

    async def test_silence_remarks_go_to_the_brain_while_she_talks(self):
        session = Session()
        session._tts_playing = {'idx': 0}
        self.ns['_dialog_sessions'] = {session}
        self.http.response = Response(data={'ok': True, 'silence_remarks': 'rare', 'choices': ['off', 'rare', 'normal'],
                                            'interval_s': 90})
        result = await self.ns['build_f_conversation_set'](self.control('conversation', {'silence_remarks': 'rare'}))
        self.assertEqual((result['silence_remarks'], result['interval_s']), ('rare', 90))
        self.assertEqual(self.http.calls[0][0], 'http://127.0.0.1:5201/api/build_f/conversation')


if __name__ == '__main__':
    unittest.main()
