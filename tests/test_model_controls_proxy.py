"""The new website controls stay same-origin and target fixed local routes."""
import ast
import asyncio
import copy
import json
import unittest
from test_wipe_proxy import SOURCE, FakeHTTP, Request, Response, Session, HTTPException


class ControlProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.http = FakeHTTP()
        self.http.get = self.http.post
        self.ns = {'asyncio': asyncio, 'json': json, 'aiohttp': self.http, 'Request': Request,
                   'HTTPException': HTTPException, '_dialog_sessions': set(),
                   '_wipe_in_progress': False, 'HANE_URL': 'http://127.0.0.1:5201'}
        wanted = {'_build_f_session_busy', '_build_f_control', 'build_f_meter_reset',
                  'build_f_models', 'build_f_select_models', 'build_f_wipe', '_retire_wiped_sessions',
                  '_reset_options', '_wait_sessions_idle', '_brain_refusal', 'build_f_unlock',
                  'build_f_conversation_get', 'build_f_conversation_set'}
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        nodes = [copy.deepcopy(n) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in wanted]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(nodes, type_ignores=[]), '<controls>', 'exec'), self.ns)

    def request(self, action='reset-meter', value=None, **kwargs):
        return Request(body=json.dumps(value or {'action': 'reset_display'}).encode(),
                       headers={'x-build-f-action': action, **kwargs.pop('headers', {})}, **kwargs)

    async def test_reset_projection_and_fixed_target(self):
        self.http.response = Response(data={'ok': True, 'usage': {'priced_known_usd': 1},
                                           'display_window': {'count': 1}, 'private': 'hidden'})
        result = await self.ns['build_f_meter_reset'](self.request())
        self.assertNotIn('private', result)
        url, request = self.http.calls[0]
        self.assertEqual(url, 'http://127.0.0.1:5201/api/build_f/meter/reset')
        self.assertFalse(request['allow_redirects'])
        self.assertEqual(request['headers'], {'X-Build-F-Action': 'reset-meter'})

    async def test_bad_origin_missing_action_busy_and_payload_rejected(self):
        cases = [(self.request(origin='https://evil.test'), 403),
                 (self.request(action='wrong'), 403),
                 (self.request(headers={'content-type': 'text/plain'}), 415),
                 (self.request(value=['bad']), 400),
                 (self.request(value={'x': 'x'*9000}), 400)]
        for request, status in cases:
            with self.assertRaises(HTTPException) as caught:
                await self.ns['build_f_meter_reset'](request)
            self.assertEqual(caught.exception.status_code, status)
        session = Session()
        session._tts_playing = {'idx': 0}
        self.ns['_dialog_sessions'].add(session)
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_meter_reset'](self.request())
        self.assertEqual(caught.exception.status_code, 409)
        self.assertFalse(self.http.calls)

    async def test_model_selection_forwarded_without_arbitrary_url(self):
        value = {'selections': {'surface': 's', 'deep': 'd', 'reflection': 'r', 'memory_write': 'm'}}
        self.http.response = Response(data={'ok': True, **value, 'options': {}, 'secret': 'omitted'})
        result = await self.ns['build_f_select_models'](self.request('select-models', value))
        self.assertEqual(result['selections'], value['selections'])
        self.assertNotIn('secret', result)
        self.assertEqual(self.http.calls[0][0], 'http://127.0.0.1:5201/api/build_f/models')

    async def test_uncertain_result_not_reported_as_success(self):
        for response in [Response(status=503), Response(data={'ok': False}), FakeHTTP.ClientError('lost')]:
            self.http.response = response
            with self.assertRaises(HTTPException) as caught:
                await self.ns['build_f_meter_reset'](self.request())
            self.assertEqual(caught.exception.status_code, 503)

    async def test_control_claims_shared_gate_before_body_await_and_excludes_wipe(self):
        entered, release = asyncio.Event(), asyncio.Event()
        request = self.request()
        async def body():
            entered.set()
            await release.wait()
            return b'{"action":"reset_display"}'
        request.body = body
        self.http.response = Response(data={'ok': True, 'usage': {}, 'display_window': {}})
        running = asyncio.create_task(self.ns['build_f_meter_reset'](request))
        await entered.wait()
        try:
            self.assertTrue(self.ns['_wipe_in_progress'])
            for fn, other in [('build_f_select_models', self.request('select-models', {'selections': {}})),
                              ('build_f_wipe', Request())]:
                with self.assertRaises(HTTPException) as caught:
                    await self.ns[fn](other)
                self.assertEqual(caught.exception.status_code, 409)
                self.assertTrue(self.ns['_wipe_in_progress'])
            self.assertEqual(self.http.calls, [])
        finally:
            release.set()
            await running
        self.assertFalse(self.ns['_wipe_in_progress'])

    async def test_cancelled_or_invalid_body_releases_gate_without_retiring_session(self):
        session = Session()
        self.ns['_dialog_sessions'].add(session)
        request = self.request()
        async def cancelled():
            self.assertTrue(self.ns['_wipe_in_progress'])
            raise asyncio.CancelledError()
        request.body = cancelled
        with self.assertRaises(asyncio.CancelledError):
            await self.ns['build_f_meter_reset'](request)
        self.assertFalse(self.ns['_wipe_in_progress'])
        self.assertFalse(session._wipe_retired)
        self.assertFalse(session.ws.closed)
        invalid = self.request()
        invalid.data = b'[]'
        with self.assertRaises(HTTPException) as caught:
            await self.ns['build_f_meter_reset'](invalid)
        self.assertEqual(caught.exception.status_code, 400)
        self.assertFalse(self.ns['_wipe_in_progress'])
        self.assertFalse(session._wipe_retired)

    async def test_model_get_fixed_route_and_filters_private_fields(self):
        self.http.response = Response(data={'ok': True, 'selections': {}, 'options': {},
                                           'presets': [], 'benchmark': 'Reviewed', 'private': 'secret'})
        result = await self.ns['build_f_models']()
        self.assertEqual(result['benchmark'], 'Reviewed')
        self.assertNotIn('private', result)
        self.assertEqual(self.http.calls[0][0], 'http://127.0.0.1:5201/api/build_f/models')
        self.assertFalse(self.http.calls[0][1]['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
