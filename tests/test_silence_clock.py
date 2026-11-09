"""Her silence remark ("you're quiet") counts from the moment HER VOICE stops, never while she speaks; the
silence_remarks setting (off / rare / normal) and the ~4-sentence voice reply (2026-11-09, items 14 and 16).

The owner: "start counting when she finishes talking, not after she begins talking". A turn's text ends long before
its last clip has played; the old clock started at the end of the text, so a long answer was followed by "why are you
so quiet?" a few seconds after she stopped talking. webui.py's idle functions are AST-extracted (the technique of the
prompt tests) and run against a fake clock; the setting's route runs on the real bridge with a fake app.
"""
import inspect
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _po_support import extract_webui, prepare_prompt_namespace  # noqa: E402
import po_contract as pc  # noqa: E402
import test_f_bridge  # noqa: E402

INSTRUCTION_END = "以及你的想法和动作。"


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SilenceClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = prepare_prompt_namespace(extract_webui())

    def setUp(self):
        ns = self.ns
        self.clock = Clock()
        ns["_time"] = self.clock
        ns.update(_LAST_SID="sid-1", _last_activity_ts=self.clock.now, _idle_fired=False, _CURRENT_CHANNEL="",
                  SILENCE_REMARKS="normal")
        ns["_voice_pending"].clear()
        ns["_ws_active"].clear()

    def turn(self, tid, text_seconds=5):
        """One of her turns: its text is generated (the turn is active), then the generation ends."""
        self.ns["_voice_started"](tid)
        self.ns["_ws_active"][tid] = {}
        self.clock.advance(text_seconds)
        self.ns["_ws_active"].pop(tid)
        self.ns["_mark_activity"]()

    def quiet_remark_due(self):
        return self.ns["_idle_check_and_arm"]()

    def test_no_remark_while_her_voice_still_plays(self):
        self.turn("t1")
        self.clock.advance(45)                          # her answer is long: the audio plays on after the text
        self.assertFalse(self.quiet_remark_due())
        self.ns["_voice_stopped"]("t1")                 # speech_done: her last clip has played
        self.clock.advance(29)
        self.assertFalse(self.quiet_remark_due())
        self.clock.advance(2)
        self.assertTrue(self.quiet_remark_due())        # 31 s after her voice stopped
        self.assertFalse(self.quiet_remark_due())       # once per silence

    def test_rare_is_three_times_the_interval_and_off_is_never(self):
        self.ns["SILENCE_REMARKS"] = "rare"
        self.turn("t1")
        self.ns["_voice_stopped"]("t1")
        self.clock.advance(80)
        self.assertFalse(self.quiet_remark_due())
        self.clock.advance(11)
        self.assertTrue(self.quiet_remark_due())
        self.assertIn("一分半钟", self.ns["_idle_deep_request"](self.ns["_idle_interval"]()))
        self.assertEqual(self.ns["_idle_deep_request"](30), self.ns["IDLE_DEEP_REQUEST"])
        self.ns["SILENCE_REMARKS"] = "off"
        self.ns["_mark_activity"]()
        self.clock.advance(3600)
        self.assertFalse(self.quiet_remark_due())
        self.assertIsNone(self.ns["_idle_interval"]())

    def test_a_cancelled_turn_does_not_hold_the_clock(self):
        self.turn("t1")
        self.ns["_voice_dropped"]("t1")                 # cancelled or failed: nothing of it will play
        self.clock.advance(31)
        self.assertTrue(self.quiet_remark_due())

    def test_a_text_channel_turn_counts_from_when_its_text_is_sent(self):
        self.ns["_CURRENT_CHANNEL"] = "discord"
        self.turn("msg-1")
        self.assertEqual(self.ns["_voice_pending"], {})
        self.clock.advance(31)
        self.assertTrue(self.quiet_remark_due())

    def test_his_message_ends_what_she_was_saying(self):
        self.turn("t1")
        self.ns["_voice_stopped"](None)                 # ws_message: he talks over her (or after her)
        self.clock.advance(31)
        self.assertTrue(self.quiet_remark_due())

    def test_a_speech_done_that_never_comes_stops_holding_the_clock(self):
        self.turn("t1")
        self.clock.advance(self.ns["VOICE_PENDING_MAX_S"] + 1)     # the page closed mid-sentence
        self.assertTrue(self.quiet_remark_due())

    def test_speech_done_ends_earlier_turns_but_not_a_later_one(self):
        self.turn("t1")
        self.turn("t2")                                 # e.g. a proactive turn queued behind her answer
        self.ns["_voice_stopped"]("t1")
        self.assertEqual(list(self.ns["_voice_pending"]), ["t2"])
        self.clock.advance(31)
        self.assertFalse(self.quiet_remark_due())
        self.ns["_voice_stopped"]("t2")
        self.clock.advance(31)
        self.assertTrue(self.quiet_remark_due())


class VoiceReplyLengthTests(unittest.TestCase):
    """Prompt level only: a spoken reply is asked for about four sentences (unless he asks for a story); text keeps
    the long form. The note opens the per-turn instruction line, after the cached prefix."""

    @classmethod
    def setUpClass(cls):
        ns = cls.ns = prepare_prompt_namespace(extract_webui())
        ns["build_memories_block"] = lambda *a, **k: "MEMORY"
        ns["_unconsolidated_turns"] = lambda *a, **k: []
        ns["CONVERSATION_HISTORY"][:] = [{"turn_id": "now", "turn_num": 1, "ts": "2026-09-25 21:30:00",
                                          "user": "Tell me about your day.", "f_user_text": "Tell me about your day."}]

    def deep(self, channel="", voice=True):
        self.ns["_CURRENT_CHANNEL"], self.ns["_CURRENT_VOICE"] = channel, voice
        kwargs = {"reply_lang": "en"} if "reply_lang" in inspect.signature(self.ns["build_messages"]).parameters else {}
        parts = self.ns["build_messages"]("Tell me about your day.", **kwargs)
        lines = [ln for ln in parts["system"].splitlines() if ln.strip()]
        return parts, lines[-2].strip()

    def test_a_spoken_reply_is_asked_to_stay_short(self):
        parts, instruction = self.deep()
        self.assertTrue(instruction.startswith(self.ns["VOICE_REPLY_NOTE"]), instruction)
        self.assertIn("四句左右", instruction)
        self.assertIn("讲个故事", instruction)
        self.assertTrue(instruction.endswith(INSTRUCTION_END))
        self.assertNotIn("四句左右", parts["system_static"])          # the cached prefix does not change

    def test_text_keeps_the_long_form(self):
        for channel, voice in (("discord", True), ("telegram", True), ("", False)):
            _parts, instruction = self.deep(channel, voice)
            self.assertNotIn("四句左右", instruction, (channel, voice))
            self.assertTrue(instruction.endswith(INSTRUCTION_END))

    def test_static_prefix_identical_for_voice_and_text(self):
        voice, _ = self.deep()
        text, _ = self.deep("discord")
        self.assertEqual(voice["system_static"], text["system_static"])
        self.assertEqual(pc.leftover_placeholders(voice["system"]), [])


class Request:
    def __init__(self, method="GET", value=None):
        self.method, self.value = method, value
        self.headers = {"X-Build-F-Action": "conversation"}
        self.is_json = True

    def get_json(self, **kwargs):
        return self.value


class SilenceSettingRouteTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_f_bridge.BridgeTests()
        self.fixture.setUp()
        self.fixture.install()
        self.g = self.fixture.g
        self.route = self.g["app"].view_functions["/api/build_f/conversation"]
        self.config = self.fixture.root / "config" / "build_f.json"

    def tearDown(self):
        self.fixture.tearDown()

    def call(self, method="GET", value=None):
        self.g["request"] = Request(method, value)
        return self.route()

    def test_default_is_normal_and_a_change_is_stored_and_applied_at_once(self):
        self.assertEqual(self.call()["silence_remarks"], "normal")
        result = self.call("POST", {"silence_remarks": "rare"})
        self.assertEqual((result["silence_remarks"], result["interval_s"]), ("rare", 90))
        self.assertEqual(self.g["SILENCE_REMARKS"], "rare")
        stored = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertEqual(stored["silence_remarks"], "rare")
        self.assertEqual(stored["test_budget_usd"], 20)                # the rest of build_f.json is kept
        self.assertIsNone(self.call("POST", {"silence_remarks": "off"})["interval_s"])

    def test_bad_values_are_refused(self):
        for value in ({"silence_remarks": "often"}, {"silence_remarks": "rare", "x": 1}, {}):
            self.assertEqual(self.call("POST", value)[1], 400, value)
        request = Request("POST", {"silence_remarks": "off"})
        request.headers["Origin"] = "https://elsewhere.invalid"
        self.g["request"] = request
        self.assertEqual(self.route()[1], 403)
        self.assertEqual(self.g["SILENCE_REMARKS"], "normal")

    def test_the_brain_reads_it_at_start(self):
        config = json.loads(self.config.read_text(encoding="utf-8"))
        config["silence_remarks"] = "off"
        self.config.write_text(json.dumps(config), encoding="utf-8")
        again = test_f_bridge.BridgeTests()
        again.setUp()
        try:
            again.g["__file__"] = self.g["__file__"]
            test_f_bridge.f_bridge.install(again.g)
            self.assertEqual(again.g["SILENCE_REMARKS"], "off")
        finally:
            again.tearDown()

    def test_speech_done_stops_the_voice_clock(self):
        stopped = []
        self.g["_voice_stopped"] = stopped.append
        self.fixture.socket.handlers["speech_done"]({"turn_id": "t-9"})
        self.assertEqual(stopped, ["t-9"])


if __name__ == "__main__":
    unittest.main()
