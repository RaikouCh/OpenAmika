"""launch.py and her ports: a bind test (not a connect), Windows' reserved port ranges, and a reserved port moving to
the next free one in settings.json. Offline; only ports the tests open themselves are bound."""
import importlib.util
import json
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("openamika_launch_ports", ROOT / "launch.py")
launch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launch)

NETSH = """
Protocol tcp Port Exclusion Ranges

Start Port    End Port
----------    --------
      5357        5357
     50000       50059     *
     52950       53049
     64000       64099

* - Administered port exclusions.
"""


def test_the_excluded_ranges_are_read_from_netsh():
    assert launch.parse_excluded_ranges(NETSH) == [(5357, 5357), (50000, 50059), (52950, 53049), (64000, 64099)]
    assert launch.parse_excluded_ranges("") == [] and launch.parse_excluded_ranges("Start Port    End Port") == []
    assert launch.range_of(53000, launch.parse_excluded_ranges(NETSH)) == (52950, 53049)
    assert launch.range_of(5202, launch.parse_excluded_ranges(NETSH)) is None


def test_a_bind_tells_free_from_in_use():
    with socket.socket() as holder:
        holder.bind(("127.0.0.1", 0))
        holder.listen()
        port = holder.getsockname()[1]
        assert launch.bind_state(port) == "in use"
    assert launch.bind_state(port) == ""


def test_windows_refusal_10013_is_a_reserved_port(monkeypatch):
    class Refused:
        def __init__(self, *args):
            pass

        def bind(self, address):
            error = PermissionError(13, "An attempt was made to access a socket in a way forbidden by its access permissions")
            error.winerror = 10013
            raise error

        def close(self):
            pass

    monkeypatch.setattr(launch.socket, "socket", Refused)
    assert launch.bind_state(53000) == "reserved"


def test_the_next_free_port_skips_the_reserved_ranges_and_her_other_ports():
    ranges = launch.parse_excluded_ranges(NETSH)
    assert launch.next_free_port(53000, ranges, avoid=set(), state=lambda p: "") == 53050
    assert launch.next_free_port(53000, ranges, avoid={53050}, state=lambda p: "") == 53051
    busy = {53050, 53051}
    assert launch.next_free_port(53000, ranges, avoid=set(), state=lambda p: "in use" if p in busy else "") == 53052
    assert launch.next_free_port(65535, ranges, avoid=set(), state=lambda p: "") is None


def settings(tmp_path):
    cfg = json.loads((ROOT / "settings.example.json").read_text("utf-8"))
    cfg["vision"]["enabled"] = True
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(cfg, indent=2), "utf-8")
    return path


def test_a_reserved_port_moves_in_settings_json_and_nothing_else_changes(tmp_path):
    path = settings(tmp_path)
    before = json.loads(path.read_text("utf-8"))
    ranges = [(52950, 53049), (8000, 8010)]
    reserved = {53000, 8002}
    moves = launch.move_reserved_ports(path, state=lambda p: "reserved" if launch.range_of(p, ranges) else "",
                                       ranges=ranges, taken={})
    after = json.loads(path.read_text("utf-8"))
    assert {(m[0], m[2], m[3]) for m in moves} == {("web/speech port", 53000, 53050), ("TTS port", 8002, 8012)}
    assert after["chat_port"] == 53050                       # 8011 is the embedder's port, so the voice gets 8012
    assert after["tts_url"] == "http://127.0.0.1:8012"
    assert after["services"]["tts"]["command"][2:4] == ["--port", "8012"]
    assert after["services"]["tts"]["health"] == "http://127.0.0.1:8012/ping"
    for key in ("brain_port", "messengers_port", "embedder", "vision", "brain_python", "_readme"):
        assert after[key] == before[key], key
    assert json.loads((tmp_path / "settings.json.bak").read_text("utf-8")) == before
    assert not reserved & {after["chat_port"], after["brain_port"], after["embedder"]["port"]}


def test_nothing_moves_when_no_port_is_reserved_or_a_program_holds_it(tmp_path):
    path = settings(tmp_path)
    text = path.read_text("utf-8")
    assert launch.move_reserved_ports(path, state=lambda p: "", ranges=[], taken={}) == []
    assert launch.move_reserved_ports(path, state=lambda p: "in use", ranges=[], taken={}) == []
    assert path.read_text("utf-8") == text and not (tmp_path / "settings.json.bak").exists()


def test_a_voice_server_hers_does_not_start_is_never_moved(tmp_path):
    path = settings(tmp_path)
    cfg = json.loads(path.read_text("utf-8"))
    del cfg["services"]["tts"]                                 # an external voice server on tts_url
    path.write_text(json.dumps(cfg), "utf-8")
    assert [e[0] for e in launch.own_port_settings(cfg)] == ["web/speech port", "brain port", "messengers port",
                                                             "embedder port", "vision port"]


@pytest.fixture()
def quiet(tmp_path, monkeypatch):
    monkeypatch.setattr(launch, "listeners", lambda: {})
    monkeypatch.setattr(launch, "TTS_ENGINE", tmp_path / "vendor" / "tts-engine")
    monkeypatch.setattr(launch, "AVATAR_MODELS", tmp_path / "avatar" / "models")
    monkeypatch.setattr(launch, "INSTANCE", tmp_path / "logs" / "instance.json")
    monkeypatch.setattr(launch, "excluded_port_ranges", lambda: [(52950, 53049)])
    return tmp_path


def rows(report):
    return {c["name"]: (c["level"], c["detail"]) for c in report.checks}


def test_the_preflight_binds_instead_of_connecting(quiet, monkeypatch):
    cfg = json.loads((ROOT / "settings.example.json").read_text("utf-8"))
    cfg["tts_url"] = "http://127.0.0.1:1"
    monkeypatch.setattr(launch, "bind_state", lambda port, host="127.0.0.1": "reserved" if port == 53000 else "")
    got = rows(launch.preflight(cfg, None, None, None, None, [], [], []))
    level, detail = got["web/speech port"]
    assert level == "err" and "reserved by Windows (excluded range 52950-53049" in detail and "chat_port" in detail
    assert got["brain port"] == ("ok", "5202 free")


def test_a_failed_start_keeps_the_window_open_and_names_the_log(tmp_path):
    """Start_OpenAmika.bat sets OPENAMIKA_PAUSE_ON_ERROR=1 before it starts the launcher in its own window."""
    import os
    import subprocess
    import sys
    bat = (ROOT / "Start_OpenAmika.bat").read_text("ascii")
    assert bat.index('set "OPENAMIKA_PAUSE_ON_ERROR=1"') < bat.index('start "OpenAmika"')
    shutil_copy = (tmp_path / "launch.py")
    shutil_copy.write_bytes((ROOT / "launch.py").read_bytes())
    (tmp_path / "settings.json").write_text("{ not json", "utf-8")
    p = subprocess.run([sys.executable, "-B", "-X", "utf8", str(shutil_copy)], cwd=tmp_path, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=120,
                       env={**os.environ, "OPENAMIKA_PAUSE_ON_ERROR": "1"})
    assert p.returncode == 1
    lines = [ln for ln in p.stderr.splitlines() if ln.strip()]
    assert any("could not start" in ln for ln in lines)
    assert any(str(tmp_path / "logs" / "launcher.log") in ln for ln in lines)
    assert "Traceback" in (tmp_path / "logs" / "launcher.log").read_text("utf-8")


def test_a_moved_port_is_a_visible_row_with_her_new_page(quiet, monkeypatch):
    cfg = json.loads((ROOT / "settings.example.json").read_text("utf-8"))
    cfg["chat_port"], cfg["tts_url"] = 53050, "http://127.0.0.1:1"
    monkeypatch.setattr(launch, "bind_state", lambda port, host="127.0.0.1": "")
    moves = [("web/speech port", ("chat_port",), 53000, 53050, (52950, 53049))]
    got = rows(launch.preflight(cfg, None, None, None, None, [], [], [], port_moves=moves))
    level, detail = got["web/speech port"]
    assert level == "warn" and "moved to 53050 in settings.json (chat_port)" in detail
    assert "her page is now http://localhost:53050" in detail
