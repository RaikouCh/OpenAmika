"""An utterance is committed once (2026-11-09, item 15, the OpenAmika side of a hosted bug): a stop after the commit
(push-to-talk released, the Stop button) committed the already-committed utterance again and she answered twice.
force_stop commits only an utterance still in progress, and a commit repeating the previous one within 5 s (compared
lower-cased, without punctuation and spaces) is dropped. DialogSession's methods lifted out of speech/api.py by AST;
no models, no audio."""
import ast
import copy
import unittest
from types import SimpleNamespace
from typing import Optional

from test_wipe_proxy import SOURCE


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now


def lift(names):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DialogSession')
    nodes = [copy.deepcopy(n) for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    return nodes


class Brain:
    def __init__(self):
        self.commits, self.messages = [], []

    async def send_commit(self, turn_id):
        self.commits.append(turn_id)

    async def send_message(self, text, turn_id, my_partial=None, **kwargs):
        self.messages.append((text, turn_id))


class CommitOnceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.asr_text = ''
        space = {'logger': SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, debug=lambda *a: None),
                 '_now_ms': lambda: 1, 'time': self.clock, 'Optional': Optional,
                 'np': SimpleNamespace(concatenate=lambda frames: frames),
                 '_is_trivial_utterance': lambda text: not text, 'stt_carry': None}

        async def asr(audio):
            return self.asr_text, self.asr_text
        space['_asr_async'] = asr
        nodes = lift({'_duplicate_commit', '_do_commit', 'force_stop'})
        exec(compile(ast.Module(nodes, type_ignores=[]), '<session>', 'exec'), space)
        events = self.events = []
        self.brain = brain = Brain()
        ids = iter(f'fresh-{i}' for i in range(100))

        class Session:
            DUPLICATE_COMMIT_S = 5.0
            _duplicate_commit, _do_commit, force_stop = (space['_duplicate_commit'], space['_do_commit'],
                                                         space['force_stop'])

            def __init__(self):
                self._peer, self.hane = 'test', brain
                self._speech_frames, self._state = [], 'IDLE'
                self._pending_partial, self._pending_chunks = None, []
                self._last_partial = self._last_partial_raw = self._last_commit_text = ''
                self._current_sent_id = self._committed_turn_id = None
                self._my_partial_pending, self._carry_text, self._last_commit_key = None, '', None

            async def _send(self, event):
                events.append(event)

            async def consume_context(self, turn_id):
                pass

            def _reset_tts_for_new_turn(self):
                pass

            def _tl_open_voice_round(self, *args, **kwargs):
                pass

            def _maybe_substitute_noise(self, text):
                return text

            def _make_turn_id(self):
                return next(ids)

            def _reset_utterance(self):
                self._speech_frames, self._state, self._last_partial = [], 'IDLE', ''

        self.session = Session()

    def speak(self, text, partial_id='p-1', state='SHORT_PAUSE'):
        """He said text; its partial went out as partial_id; the VAD is in `state`."""
        s = self.session
        s._speech_frames, s._state = ['frame'], state
        s._last_partial = s._last_partial_raw = text
        s._current_sent_id = partial_id

    def commits(self):
        return [e for e in self.events if e.get('type') == 'commit' and e.get('text')]

    async def test_a_stop_after_the_commit_does_not_commit_again(self):
        self.speak('Hello there, how was your day?')
        await self.session._do_commit()                 # the long pause commits it
        self.session._state = 'POST_COMMIT'             # its audio stays until her protect
        self.clock.now += 6                              # past the 5 s rule: only force_stop's own check holds
        await self.session.force_stop()                 # push-to-talk released / the Stop button
        self.assertEqual(self.brain.commits, ['p-1'])
        self.assertEqual(self.brain.messages, [])
        self.assertEqual(len(self.commits()), 1)
        self.assertEqual(self.session._speech_frames, [])

    async def test_a_stop_while_he_still_speaks_commits_what_he_said(self):
        self.speak('Wait, one more thing', state='SPEAKING')
        await self.session.force_stop()
        self.assertEqual(self.brain.commits, ['p-1'])

    async def test_the_same_text_again_within_five_seconds_is_dropped(self):
        self.speak('Hello there, how was your day?')
        await self.session._do_commit()
        self.clock.now += 3
        self.speak('hello there how was your day', partial_id='p-2')     # the same words, another partial id
        await self.session._do_commit()
        self.assertEqual(self.brain.commits, ['p-1'])
        self.clock.now += 6                              # later, he may say it again
        self.speak('Hello there, how was your day?', partial_id='p-3')
        await self.session._do_commit()
        self.assertEqual(self.brain.commits, ['p-1', 'p-3'])

    async def test_a_fresh_transcript_is_deduplicated_too(self):
        self.asr_text = 'Good morning!'
        for _ in range(2):
            self.session._speech_frames, self.session._state, self.session._current_sent_id = ['frame'], 'SHORT_PAUSE', None
            await self.session._do_commit()
        self.assertEqual(self.brain.messages, [('Good morning!', 'fresh-0')])

    async def test_different_words_are_never_dropped(self):
        self.speak('Yes.')
        await self.session._do_commit()
        self.speak('Yes, please.', partial_id='p-2')
        await self.session._do_commit()
        self.assertEqual(self.brain.commits, ['p-1', 'p-2'])


if __name__ == '__main__':
    unittest.main()
