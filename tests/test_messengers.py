"""messengers/: config handling, her words as text, message splitting, and the outbox's turn handling."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "messengers") not in sys.path:
    sys.path.insert(0, str(ROOT / "messengers"))

import core  # noqa: E402
import service  # noqa: E402


# ───────────────────────────── config ─────────────────────────────
def test_load_missing_file_is_defaults(tmp_path):
    cfg = core.load_config(tmp_path / "nope.json")
    assert cfg["discord"] == {"enabled": False, "token": "", "allowed_users": []}
    assert cfg["state"]["last_chat"] is None


def test_load_merges_and_normalises(tmp_path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"telegram": {"enabled": True, "token": " abc ", "allowed_users": ["7", 3, "x", -1]},
                                "state": {"last_chat": {"platform": "telegram", "chat_id": "7"}}}), "utf-8")
    cfg = core.load_config(path)
    assert cfg["telegram"] == {"enabled": True, "token": "abc", "allowed_users": [3, 7]}
    assert cfg["discord"]["enabled"] is False
    assert cfg["state"]["last_chat"]["chat_id"] == "7"


def test_parse_ids_accepts_strings_and_lists():
    assert core.parse_ids("123, 456;789 123") == [123, 456, 789]
    assert core.parse_ids([1, "2", "junk", 0, None]) == [1, 2]
    assert core.parse_ids(None) == []


def test_apply_update_keeps_token_when_blank_and_clears_on_request():
    cfg = core.default_config()
    cfg["discord"].update(token="tok-saved-1234", enabled=True, allowed_users=[1])
    out = core.apply_update(cfg, {"discord": {"token": "", "allowed_users": "5, 6", "enabled": True}})
    assert out["discord"] == {"enabled": True, "token": "tok-saved-1234", "allowed_users": [5, 6]}
    out = core.apply_update(out, {"discord": {"clear_token": True}})
    assert out["discord"]["token"] == "" and out["discord"]["enabled"] is False     # nothing to connect with
    out = core.apply_update(out, {"telegram": {"token": "new", "enabled": True}})
    assert out["telegram"]["enabled"] is True and out["telegram"]["token"] == "new"
    assert cfg["discord"]["token"] == "tok-saved-1234"                               # the input is untouched


def test_public_view_masks_tokens():
    cfg = core.default_config()
    cfg["telegram"].update(token="123456:ABCDEFxyz", allowed_users=[42])
    view = core.public_view(cfg)
    assert view["telegram"] == {"enabled": False, "token_present": True, "token_hint": "…Fxyz", "allowed_users": ["42"]}
    assert "123456:ABCDEFxyz" not in json.dumps(view) and "ABCDEF" not in json.dumps(view)


def test_save_and_reload_round_trip(tmp_path):
    cfg = core.default_config()
    cfg["discord"].update(enabled=True, token="t", allowed_users=[9])
    core.save_config(cfg, tmp_path / "m.json")
    assert core.load_config(tmp_path / "m.json") == cfg


# ───────────────────────────── her words ─────────────────────────────
def test_her_text_strips_stage_markup():
    assert core.her_text("（中文）【Laugh】好呀，[casual_happy] 那就这么定了。【想想】") == "好呀， 那就这么定了。"
    assert core.her_text("status: ok\ntone: casual_happy\nreply: hi there\n\n  \nsecond line\\nthird") == "hi there\nsecond line\nthird"
    assert core.her_text("") == "" and core.her_text(None) == ""


def test_split_message_prefers_paragraphs_then_sentences():
    text = "First paragraph here.\n\nSecond paragraph is here. It has two sentences. " + "x" * 30
    pieces = core.split_message(text, 60)
    assert all(len(p) <= 60 for p in pieces)
    assert pieces[0] == "First paragraph here."
    assert "".join(p.replace(" ", "") for p in pieces) == text.replace(" ", "").replace("\n", "")
    assert core.split_message("short", 2000) == ["short"]
    assert core.split_message("a" * 100, 40) == ["a" * 40, "a" * 40, "a" * 20]
    assert core.split_message("", 10) == []


def test_her_channel_cue_names_where_she_is_and_that_pictures_do_not_reach_her():
    discord = core.turn_context("discord")
    assert "他自己服务器上的 Discord 频道" in discord and "“我在你服务器上的 Discord 频道”" in discord
    assert "图片和语音到不了你这儿" in discord and "不要声效" in discord
    telegram = core.turn_context("telegram")
    assert "Telegram" in telegram and "图片和语音到不了你这儿" in telegram and "Discord" not in telegram


def test_incoming_text_is_one_trimmed_line_with_a_cap():
    assert core.incoming_text("  hi\r\nthere   you ") == "hi there you"
    assert len(core.incoming_text("y" * 5000)) == core.MAX_INCOMING


def test_replies_from_events():
    assert core.replies_from("surface_done", {"reply": "【Sigh】okay."}) == ["okay."]
    assert core.replies_from("deep_done", {"speech": "the real answer", "thought": "private"}) == ["the real answer"]
    assert core.replies_from("deep_done", {"speech": ""}) == []
    assert core.replies_from("begin", {"proactive": True}) == []
    assert core.replies_from("error", {"message": "boom"}) == ["⚠ OpenAmika: boom"]


def test_light_levels():
    assert core.light(False, {})["level"] == "err"
    assert core.light(True, {"discord": {"enabled": False}})["level"] == "warn"
    assert core.light(True, {"discord": {"enabled": True, "connected": False, "error": "token rejected"}}) == \
        {"level": "err", "detail": "Discord: token rejected"}
    assert core.light(True, {"telegram": {"enabled": True, "connected": False, "error": ""}})["level"] == "warn"
    assert core.light(True, {"telegram": {"enabled": True, "connected": True, "name": "@amika_bot", "error": ""}}) == \
        {"level": "ok", "detail": "ready · Telegram @amika_bot"}


# ───────────────────────────── the outbox ─────────────────────────────
class FakeBrain:
    def __init__(self):
        self.connected, self.sent, self.protected, self.spoken = True, [], 0, []

    async def send(self, text, turn_id, context, channel=""):
        self.sent.append((text, turn_id, context))
        self.channels = getattr(self, "channels", []) + [channel]

    async def protect(self):
        self.protected += 1

    async def speech_done(self, turn_id):
        self.spoken.append(turn_id)


class FakeChat(service.Chat):
    platform = "telegram"

    def __init__(self, label="fake chat"):
        super().__init__("1", label)
        self.out, self.closed_calls = [], 0

    async def send(self, text):
        self.out.append(text)

    def closed(self):
        self.closed_calls += 1


class FakeService:
    def __init__(self, last=None):
        self.brain, self.last = FakeBrain(), last
        self.outbox = service.Outbox(self)

    async def last_chat(self):
        return self.last


def test_outbox_runs_one_turn_and_protects_after_the_first_send():
    async def scenario():
        svc = FakeService()
        chat = FakeChat()
        worker = asyncio.create_task(svc.outbox.run())
        await svc.outbox.put(chat, "hello there", "telegram")
        await asyncio.sleep(0.05)
        assert len(svc.brain.sent) == 1 and svc.brain.sent[0][0] == "hello there"
        assert "Telegram" in svc.brain.sent[0][2]
        turn_id = svc.brain.sent[0][1]
        ob = svc.outbox
        await ob.on_event("begin", {"turn_id": turn_id})
        await ob.on_event("surface_done", {"turn_id": turn_id, "reply": "【Laugh】hi!"})
        assert chat.out == ["hi!"] and svc.brain.protected == 1
        await ob.on_event("deep_done", {"turn_id": turn_id, "speech": "x" * 5000})
        assert len(chat.out) == 3 and all(len(p) <= core.LIMITS["telegram"] for p in chat.out[1:])
        assert svc.brain.protected == 1                       # protected once per turn
        await ob.on_event("end", {"turn_id": turn_id})
        await asyncio.sleep(0.05)
        assert chat.closed_calls == 1 and turn_id not in ob.turns
        assert svc.brain.spoken == [turn_id]                  # "played out" = delivered: the brain may archive it
        worker.cancel()
    asyncio.run(scenario())


def test_outbox_sends_a_proactive_turn_to_her_last_chat():
    async def scenario():
        last = FakeChat("her last chat")
        svc = FakeService(last=last)
        ob = svc.outbox
        await ob.on_event("begin", {"turn_id": "open-1", "proactive": True})
        await ob.on_event("deep_done", {"turn_id": "open-1", "speech": "miss you"})
        await ob.on_event("end", {"turn_id": "open-1"})
        assert last.out == ["miss you"] and svc.brain.protected == 1 and "open-1" not in ob.turns
        assert svc.brain.spoken == ["open-1"]
        # events for a turn nobody sent (a browser's) are ignored, and so is a proactive one with no last chat
        svc2 = FakeService(last=None)
        await svc2.outbox.on_event("begin", {"turn_id": "open-2", "proactive": True})
        await svc2.outbox.on_event("deep_done", {"turn_id": "open-2", "speech": "lost"})
        await svc2.outbox.on_event("surface_done", {"turn_id": "web-9", "reply": "not mine"})
        assert svc2.outbox.turns == {} and svc2.brain.protected == 0
    asyncio.run(scenario())


def test_outbox_tells_the_sender_when_the_brain_is_down():
    async def scenario():
        svc = FakeService()
        svc.brain.connected = False
        chat = FakeChat()
        worker = asyncio.create_task(svc.outbox.run())
        await svc.outbox.put(chat, "anyone?", "telegram")
        await asyncio.sleep(0.05)
        assert chat.out and chat.out[0].startswith("⚠ OpenAmika") and chat.closed_calls == 1
        assert svc.brain.sent == [] and svc.brain.spoken == []
        worker.cancel()
    asyncio.run(scenario())


def test_bot_hints_unknown_senders_once_an_hour():
    bot = service.TelegramBot(FakeService())
    assert bot.hint_due(5) is True
    assert bot.hint_due(5) is False
    assert bot.hint_due(6) is True
    assert "5" in bot.hint_text(5) and "Telegram" in bot.hint_text(5)


@pytest.mark.parametrize("platform,limit", [("discord", 2000), ("telegram", 4096)])
def test_platform_limits(platform, limit):
    assert core.LIMITS[platform] == limit
