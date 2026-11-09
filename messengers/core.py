"""OpenAmika messengers — the parts with no network in them.

Config (config/messengers.json: tokens, allow-lists, the last chat she talked in), her words as plain text,
splitting a long reply to a platform's message limit, and what each brain event means for a text channel.
service.py wires these to the brain, Discord and Telegram; tests/test_messengers.py covers this file.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "messengers.json"

PLATFORMS = ("discord", "telegram")
LIMITS = {"discord": 2000, "telegram": 4096}          # a platform's longest message
TITLES = {"discord": "Discord", "telegram": "Telegram"}
MAX_INCOMING = 2000                                   # longer messages are cut: a turn is a few sentences, not a file

# Her raw lines can still carry what the stage uses and a text message must not show: 【SFX】 sound tags,
# 【想想】 control markers, a leading （中文） language label and leaked [register_emotion] tags.
_SFX_RE = re.compile(r"【\s*[^】\n]{1,24}\s*】")
_TAG_RE = re.compile(r"\[\s*[A-Za-z][A-Za-z_\- ,]*?\s*(?:\d+(?:\.\d+)?\s*)?\]")
_LANG_TAG_RE = re.compile(r"^\s*[（(]\s*(?:中文|日本語|日语|English|英文|英语)\s*[）)]\s*")
_FIELD_LINE_RE = re.compile(r"^\s*(status|tone|mode|reply)\s*[:：]\s*", re.I)   # a leaked surface field line


# ───────────────────────────── config ─────────────────────────────
def default_config() -> dict:
    return {"discord": {"enabled": False, "token": "", "allowed_users": []},
            "telegram": {"enabled": False, "token": "", "allowed_users": []},
            "state": {"last_chat": None}}


def load_config(path: Path = CONFIG_PATH) -> dict:
    """The file merged over the defaults; a missing or broken file is the defaults (the service still runs,
    with nothing enabled, so the Setup page can fill it in)."""
    cfg = default_config()
    try:
        raw = json.loads(Path(path).read_text("utf-8-sig"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg
    for platform in PLATFORMS:
        block = raw.get(platform)
        if isinstance(block, dict):
            cfg[platform]["enabled"] = bool(block.get("enabled"))
            cfg[platform]["token"] = str(block.get("token") or "").strip()
            cfg[platform]["allowed_users"] = parse_ids(block.get("allowed_users"))
    state = raw.get("state")
    if isinstance(state, dict) and isinstance(state.get("last_chat"), dict):
        cfg["state"]["last_chat"] = dict(state["last_chat"])
    return cfg


def save_config(cfg: dict, path: Path = CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".messengers-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(cfg, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def parse_ids(value) -> list:
    """User ids from a list or a "123, 456" string: positive integers, unique, sorted. Junk is dropped."""
    if value is None:
        return []
    items = value if isinstance(value, (list, tuple)) else re.split(r"[\s,;]+", str(value))
    out = set()
    for item in items:
        text = str(item).strip()
        if re.fullmatch(r"\d{1,20}", text) and int(text) > 0:
            out.add(int(text))
    return sorted(out)


def apply_update(cfg: dict, update: dict) -> dict:
    """A new config from the Setup page's form. Per platform: `enabled`, `allowed_users`, and `token` only
    when a non-empty one was typed (a blank field keeps the saved token; `clear_token` removes it)."""
    out = json.loads(json.dumps(cfg))
    for platform in PLATFORMS:
        block = update.get(platform) if isinstance(update, dict) else None
        if not isinstance(block, dict):
            continue
        target = out[platform]
        if "enabled" in block:
            target["enabled"] = bool(block["enabled"])
        if "allowed_users" in block:
            target["allowed_users"] = parse_ids(block["allowed_users"])
        token = str(block.get("token") or "").strip()
        if token:
            target["token"] = token
        if block.get("clear_token"):
            target["token"] = ""
        if not target["token"]:
            target["enabled"] = False      # nothing to connect with
    return out


def mask_token(token: str) -> str:
    token = str(token or "")
    return f"…{token[-4:]}" if len(token) >= 8 else ("set" if token else "")


def public_view(cfg: dict) -> dict:
    """The config as the Setup page may see it: tokens masked, the allow-lists as typed."""
    view = {}
    for platform in PLATFORMS:
        block = cfg.get(platform) or {}
        view[platform] = {"enabled": bool(block.get("enabled")), "token_present": bool(block.get("token")),
                          "token_hint": mask_token(block.get("token", "")),
                          "allowed_users": [str(i) for i in block.get("allowed_users") or []]}
    view["last_chat"] = (cfg.get("state") or {}).get("last_chat")
    return view


# ───────────────────────────── her words ─────────────────────────────
def her_text(text: str) -> str:
    """One of her lines as a plain text message."""
    t = _LANG_TAG_RE.sub("", str(text or ""))
    t = _SFX_RE.sub(" ", t)
    t = _TAG_RE.sub(" ", t)
    t = t.replace("\\n", "\n")
    lines = []
    for line in t.splitlines():
        field = _FIELD_LINE_RE.match(line)
        if field:                                   # "reply: …" keeps its words; status/tone/mode lines are hers to keep
            line = line[field.end():] if field.group(1).lower() == "reply" else ""
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def split_message(text: str, limit: int) -> list:
    """Pieces of at most `limit` characters, cut at a paragraph, then a sentence end, then a space."""
    text = str(text or "").strip()
    if not text:
        return []
    pieces = []
    while len(text) > limit:
        window = text[:limit]
        cut = -1
        for pattern in (r"\n\s*\n", r"\n", r"(?<=[。！？!?\.])\s", r"(?<=[，、,;；])\s?", r"\s"):
            hits = [m.end() for m in re.finditer(pattern, window)]
            hits = [h for h in hits if h >= limit // 3]
            if hits:
                cut = hits[-1]
                break
        if cut <= 0:
            cut = limit
        head, text = text[:cut].rstrip(), text[cut:].lstrip()
        if head:
            pieces.append(head)
    if text:
        pieces.append(text)
    return pieces


def incoming_text(text: str) -> str:
    """What the sender typed, as the brain gets it: trimmed, one message at most MAX_INCOMING characters."""
    text = " ".join(str(text or "").replace("\r", "\n").split("\n")).strip()
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text[:MAX_INCOMING]


def turn_context(platform: str) -> str:
    """The per-turn context the brain weaves into her prompts: she is texting on her phone, he is not next
    to her (they live together; a text means he is out, or in another room). Chinese, like every other cue
    she reads; the brain also swaps her scene to the text-channel one when the message carries `channel`.
    Where she is, by name: her bot lives on HIS server (or in his DMs), never "here" (a user who read "send it
    to me through here" tried the MekaHime Discord instead of his own bot); and only words reach her there."""
    where = {"discord": "你在他自己服务器上的 Discord 频道（或私信）里，提到这里就说“我在你服务器上的 Discord 频道”，别只说“这里”",
             "telegram": "在 Telegram 上和他的对话里"}.get(platform, f"在 {TITLES.get(platform, platform)} 上")
    return (f"[渠道] 这条是在 {TITLES.get(platform, platform)} 上收到的文字消息（{where}）：你是在手机上看到的，"
            f"他现在不在你身边。这里只收得到文字，图片和语音到不了你这儿。用文字回——只写要说的话，不要动作描写、不要声效。")


# ───────────────────────────── brain events ─────────────────────────────
TERMINAL_EVENTS = ("end", "error")


def replies_from(event: str, data: dict) -> list:
    """Her message(s) carried by one brain event. surface_done carries her quick line, deep_done her real
    reply (already deduplicated against the quick line by the brain); an error is told as a system line."""
    data = data or {}
    if event == "surface_done":
        text = her_text(data.get("reply"))
        return [text] if text else []
    if event == "deep_done":
        text = her_text(data.get("speech"))
        return [text] if text else []
    if event == "error":
        message = " ".join(str(data.get("message") or "the brain reported an error").split())
        return [f"⚠ OpenAmika: {message[:300]}"]
    return []


# ───────────────────────────── status ─────────────────────────────
def light(brain_connected: bool, bots: dict) -> dict:
    """The launcher's light for this service: {level: ok|warn|err, detail}. `bots` is
    {platform: {enabled, connected, name, error}}."""
    if not brain_connected:
        return {"level": "err", "detail": "not linked to the brain — is it up?"}
    enabled = {p: s for p, s in bots.items() if s.get("enabled")}
    if not enabled:
        return {"level": "warn", "detail": "no bot set up — Setup page → Text her"}
    broken = [f"{TITLES[p]}: {s['error']}" for p, s in enabled.items() if s.get("error")]
    if broken:
        return {"level": "err", "detail": " · ".join(broken)}
    waiting = [TITLES[p] for p, s in enabled.items() if not s.get("connected")]
    if waiting:
        return {"level": "warn", "detail": "connecting… " + ", ".join(waiting)}
    names = [f"{TITLES[p]} {s.get('name') or 'bot'}" for p, s in enabled.items()]
    return {"level": "ok", "detail": "ready · " + " · ".join(names)}
