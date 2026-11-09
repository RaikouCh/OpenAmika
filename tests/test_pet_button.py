"""The Use page's "Desktop pet" button: speech/pet_window.py (who may ask, which Python, the two Windows events, open /
close / install), speech/api.py's /api/pet routes and the socket's "she is in her window" answer, pet.py's side of the
hand-over, and what ships with it.

Offline and windowless: no pywebview, no WebView2, no server. Her window's process is played by a small stub script
that makes (or does not make) the two named events with pet.py's own helpers.
"""
import ast
import asyncio
import copy
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
ME = str(Path(sys.executable))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pet = _load("openamika_pet_for_button", ROOT / "pet.py")
pw = _load("openamika_pet_window", ROOT / "speech" / "pet_window.py")


def fresh_name():
    """An event name of this test's own: never the real window's."""
    return r"Local\OpenAmika-pet-test-" + uuid.uuid4().hex[:16]


class WhoMayAskTests(unittest.TestCase):
    def test_this_pc_itself(self):
        for client, host in (("127.0.0.1", "localhost:53000"), ("127.0.0.1", "127.0.0.1:53000"),
                             ("::1", "[::1]:53000"), ("::ffff:127.0.0.1", "localhost:53000"),
                             ("127.0.0.1", "LOCALHOST:53010"), ("::1%lo", "localhost")):
            self.assertTrue(pw.is_local(client, {"host": host}), (client, host))

    def test_not_another_device(self):
        self.assertFalse(pw.is_local("192.168.1.20", {"host": "192.168.1.5:53000"}))
        self.assertFalse(pw.is_local("100.101.102.103", {"host": "localhost:53000"}))     # a made-up Host does not help
        self.assertFalse(pw.is_local("fe80::1%eth0", {"host": "localhost:53000"}))
        for client in (None, "", "testclient", "localhost"):
            self.assertFalse(pw.is_local(client, {"host": "localhost:53000"}), client)

    def test_not_through_a_tunnel_or_a_proxy(self):
        # Tailscale Serve, a tunnel and a reverse proxy all arrive from 127.0.0.1: the header gives them away
        for header in pw.FORWARDED:
            self.assertFalse(pw.is_local("127.0.0.1", {"host": "localhost:53000", header: "100.64.0.2"}), header)
        self.assertIn("x-forwarded-for", pw.FORWARDED)
        self.assertIn("tailscale-user-login", pw.FORWARDED)

    def test_not_a_web_page_that_points_its_own_name_at_this_pc(self):
        for host in ("evil.example:53000", "localhost.evil.example", "pc.tail1234.ts.net", "", "[not-a-host"):
            self.assertFalse(pw.is_local("127.0.0.1", {"host": host}), host)
        self.assertFalse(pw.is_local("127.0.0.1", {}))


class WhichPythonTests(unittest.TestCase):
    def setUp(self):
        pw.forget_pywebview()
        self.addCleanup(pw.forget_pywebview)

    def test_the_launcher_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            named = str(Path(tmp) / "brain-env" / "python.exe")
            (Path(tmp) / "settings.json").write_text(json.dumps({"brain_python": "other/python.exe"}), "utf-8")
            self.assertEqual(pw.pet_python({"AMIKA_PET_PYTHON": named}, root=tmp), Path(named))

    def test_without_the_launcher_settings_then_the_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            default = root / "envs" / "brain" / "Scripts" / "python.exe"
            self.assertEqual(pw.pet_python({}, root=root), default)                    # no settings.json
            (root / "settings.json").write_text("\ufeff" + json.dumps({"brain_python": "py311/python.exe"}), "utf-8")
            self.assertEqual(pw.pet_python({}, root=root), root / "py311" / "python.exe")   # a BOM, as Notepad saves
            absolute = str(root / "elsewhere" / "python.exe")
            (root / "settings.json").write_text(json.dumps({"brain_python": absolute}), "utf-8")
            self.assertEqual(pw.pet_python({}, root=root), Path(absolute))
            for broken in ("{not json", "[]", json.dumps({"brain_python": ""}), json.dumps({"brain_python": None})):
                (root / "settings.json").write_text(broken, "utf-8")
                self.assertEqual(pw.pet_python({"AMIKA_PET_PYTHON": "  "}, root=root), default, broken)

    def test_the_launcher_passes_its_own_python(self):
        launch = (ROOT / "launch.py").read_text("utf-8")
        self.assertIn("AMIKA_PET_PYTHON=sys.executable", launch)

    def test_a_yes_is_kept_and_a_no_is_asked_again(self):
        answers, asked = [3, 0], []

        def run(command, **kwargs):
            asked.append(command)
            return SimpleNamespace(returncode=answers.pop(0))

        with mock.patch.object(pw.subprocess, "run", run):
            self.assertFalse(pw.has_pywebview("py.exe"))
            self.assertFalse(pw.has_pywebview("py.exe"))                 # a fresh no is not asked again at once
            self.assertEqual(len(asked), 1)
            self.assertEqual(asked[0][:2], ["py.exe", "-c"])
            self.assertIn('find_spec("webview")', asked[0][2])
            self.assertTrue(pw.has_pywebview("py.exe", fresh=True))      # after the install
            self.assertTrue(pw.has_pywebview("py.exe"))
            self.assertEqual(len(asked), 2)
            answers.append(0)
            pw._installed["old.exe"] = (False, time.monotonic() - pw.RECHECK_S - 1)
            self.assertTrue(pw.has_pywebview("old.exe"))                 # an old no is asked again
            answers.append(3)
            pw.forget_pywebview("py.exe")                                # her window said it is missing after all
            self.assertFalse(pw.has_pywebview("py.exe"))
            self.assertEqual(len(asked), 4)

    def test_a_python_that_does_not_run_has_none(self):
        def run(command, **kwargs):
            raise FileNotFoundError(command[0])

        with mock.patch.object(pw.subprocess, "run", run):
            self.assertFalse(pw.has_pywebview("missing.exe"))


class NameTests(unittest.TestCase):
    def test_the_page_side_and_her_window_use_one_name(self):
        self.assertEqual(pw.event_name(), pet.instance_name())
        self.assertEqual(pw.READY, pet.READY)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(pw.event_name(one), pet.instance_name(one))
            self.assertNotEqual(pw.event_name(one), pw.event_name(two))      # two installs: two windows
            self.assertRegex(pw.event_name(one), r"^Local\\OpenAmika-pet-[0-9a-f]{16}$")
            if WINDOWS:                                                      # C:\OpenAmika and c:\openamika are one
                self.assertEqual(pw.event_name(one.upper()), pw.event_name(one.lower()))

    def test_no_state_in_the_address(self):
        # what the page had on travels through PetApi.handover(), never in the address of her window's page
        self.assertEqual(pet.pet_url("http://localhost:53000"), "http://localhost:53000/use?pet=1")


class HandoverTests(unittest.TestCase):
    def test_her_page_takes_it_over_once(self):
        ready = []
        api = pet.PetApi("http://localhost:53000", power=True, mic=True, on_ready=lambda: ready.append(1))
        self.assertEqual(api.handover(), {"power": True, "mic": True})
        self.assertEqual(api.handover(), {"power": False, "mic": False})     # a reload of her page starts nothing
        self.assertEqual(ready, [1])

    def test_a_window_opened_by_hand_hands_nothing_over(self):
        self.assertEqual(pet.PetApi("http://localhost:53000").handover(), {"power": False, "mic": False})
        only_power = pet.PetApi("http://localhost:53000", power=True)
        self.assertEqual(only_power.handover(), {"power": True, "mic": False})

    def test_a_failing_ready_signal_does_not_cost_her_the_session(self):
        def broken():
            raise OSError("no event today")

        api = pet.PetApi("http://localhost:53000", power=True, on_ready=broken)
        with mock.patch.object(sys, "stderr", new=mock.Mock()):
            self.assertEqual(api.handover(), {"power": True, "mic": False})


class OtherSystemsTests(unittest.TestCase):
    def test_windows_only_and_harmless_elsewhere(self):
        with mock.patch.object(pw, "os", SimpleNamespace(name="posix")):
            self.assertFalse(pw.running("anything"))
            self.assertEqual(pw.start("http://localhost:53000")["code"], "unsupported")
            self.assertEqual(pw.install()["code"], "unsupported")
            self.assertEqual(pw.close(), {"ok": True, "was_running": False})


@unittest.skipUnless(WINDOWS, "her desktop window is Windows-only")
class EventTests(unittest.TestCase):
    def setUp(self):
        self.name, self.handles = fresh_name(), []
        self.addCleanup(lambda: pet.release(self.handles))

    def claim(self):
        handle, already = pet.claim_instance(self.name)
        self.handles.append(handle)
        return handle, already

    def test_open_means_the_event_exists(self):
        self.assertFalse(pw.running(self.name))
        handle, already = self.claim()
        self.assertTrue(handle)
        self.assertFalse(already)
        self.assertTrue(pw.running(self.name))
        self.assertFalse(pw.running(self.name + pw.READY))               # her page has not asked yet
        self.handles.append(pet.page_alive(self.name))
        self.assertTrue(pw.running(self.name + pw.READY))
        self.assertEqual(pet.claim_instance(self.name), (None, True))    # a second window leaves
        pet.release(self.handles)
        del self.handles[:]
        self.assertFalse(pw.running(self.name))                          # nothing stale after she has gone
        self.assertFalse(pw.running(self.name + pw.READY))

    def test_nothing_to_close(self):
        self.assertEqual(pw.close(self.name), {"ok": True, "was_running": False})

    def test_bring_her_back_closes_her_window(self):
        handle, _ = self.claim()
        destroyed = threading.Event()

        class Window:
            def destroy(window):                 # pywebview: webview.start() returns, main() drops the events
                pet.release(self.handles)
                del self.handles[:]
                destroyed.set()

        pet.close_when(Window(), handle)
        self.assertEqual(pw.close(self.name, wait=10), {"ok": True, "was_running": True})
        self.assertTrue(destroyed.wait(5))
        self.assertFalse(pw.running(self.name))

    def test_a_window_that_stays_is_reported(self):
        self.claim()                                                     # nobody listens to "close now"
        answer = pw.close(self.name, wait=0.3)
        self.assertFalse(answer["ok"])
        self.assertIn("did not close", answer["reason"])
        self.assertTrue(pw.running(self.name))

    def test_she_goes_with_the_server_that_opened_her(self):
        handle, _ = self.claim()
        destroyed = threading.Event()
        server = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"], stdin=subprocess.PIPE)
        self.addCleanup(server.kill)
        pet.close_when(SimpleNamespace(destroy=destroyed.set), handle, server.pid)
        self.assertFalse(destroyed.wait(0.3))                            # the server lives: so does her window
        server.stdin.close()                                             # the server stops
        server.wait(20)
        self.assertTrue(destroyed.wait(10))

    def test_a_window_that_closes_by_itself_is_not_closed_twice(self):
        handle, _ = self.claim()
        destroyed, closing = threading.Event(), threading.Event()
        pet.close_when(SimpleNamespace(destroy=destroyed.set), handle, None, closing)
        time.sleep(0.2)                                                  # the watcher is waiting by now
        closing.set()                                                    # her own ✕: main() says so, then lets go
        pet.release(self.handles)
        del self.handles[:]
        for thread in threading.enumerate():
            if thread.name == "pet-close":
                thread.join(10)
        self.assertFalse(destroyed.is_set())


STUB = r'''
import importlib.util, json, os, sys, time
from ctypes import wintypes

spec = importlib.util.spec_from_file_location("pet_for_stub", os.environ["PET_STUB_PET"])
pet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pet)
mode, name = os.environ["PET_STUB_MODE"], os.environ["PET_STUB_EVENT"]
with open(os.environ["PET_STUB_SEEN"], "w", encoding="utf-8") as out:
    json.dump({"argv": sys.argv[1:], "pid": os.getpid()}, out)
if mode == "missing":
    print("Her desktop pet needs pywebview.")
    sys.exit(2)
if mode == "gone":
    sys.exit(0)
if mode == "crash":
    raise RuntimeError("no window today")
if mode == "never":
    time.sleep(60)
    sys.exit(0)
held, already = pet.claim_instance(name)
if already:
    print("Her desktop pet window is already open.")
    sys.exit(0)
ready = None if mode == "slow" else pet.page_alive(name)
if mode == "deaf":
    time.sleep(60)                               # does not listen to "close now"
else:
    pet._kernel32().WaitForMultipleObjects(1, (wintypes.HANDLE * 1)(held), False, 60000)
pet.release([held, ready])
'''


@unittest.skipUnless(WINDOWS, "her desktop window is Windows-only")
class StartTests(unittest.TestCase):
    """pet_window.start() and close() against a stub of her window (this Python, no pywebview)."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="pet-button-", ignore_cleanup_errors=True)
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)
        self.stub, self.seen_path, self.log = self.tmp / "stub.py", self.tmp / "seen.json", self.tmp / "pet.log"
        self.stub.write_text(STUB, "utf-8")
        self.name = fresh_name()
        pw.forget_pywebview()
        pw._installed[ME] = (True, time.monotonic())
        pw._child = None
        self.addCleanup(self.clean)

    def clean(self):
        child, pw._child = pw._child, None
        if child is not None and child.poll() is None:
            pw._kill_tree(child.pid)
            child.wait(20)
        pw.forget_pywebview()

    def start(self, mode, wait=30.0, **options):
        env = {"PET_STUB_MODE": mode, "PET_STUB_EVENT": self.name, "PET_STUB_SEEN": str(self.seen_path),
               "PET_STUB_PET": str(ROOT / "pet.py"), "PYTHONDONTWRITEBYTECODE": "1"}
        with mock.patch.dict(os.environ, env):
            return pw.start("http://localhost:53000", python=ME, script=self.stub, name=self.name, wait=wait,
                            log=self.log, **options)

    def seen(self):
        return json.loads(self.seen_path.read_text("utf-8"))

    def test_she_opens_takes_over_and_comes_back(self):
        self.assertEqual(self.start("opens", power=True, mic=True), {"ok": True})
        self.assertEqual(self.seen()["argv"], ["--url", "http://localhost:53000", "--close-with", str(os.getpid()),
                                               "--power", "--mic"])
        self.assertTrue(pw.running(self.name))
        self.assertEqual(self.start("opens"), {"ok": True, "already": True})          # one window, never two
        self.assertEqual(pw.close(self.name, wait=20), {"ok": True, "was_running": True})
        self.assertFalse(pw.running(self.name))
        self.assertIsNone(pw._child)
        self.assertIn("the Use page's Desktop pet button", self.log.read_text("utf-8"))

    def test_nothing_is_handed_over_unless_it_was_on(self):
        self.assertEqual(self.start("opens"), {"ok": True})
        self.assertEqual(self.seen()["argv"], ["--url", "http://localhost:53000", "--close-with", str(os.getpid())])
        self.assertTrue(pw.close(self.name, wait=20)["ok"])

    def test_a_window_that_does_not_listen_is_stopped(self):
        self.assertEqual(self.start("deaf"), {"ok": True})
        child = pw._child
        self.assertEqual(pw.close(self.name, wait=0.5), {"ok": True, "was_running": True})
        self.assertIsNotNone(child.wait(20))                                          # her window's process has gone
        self.assertFalse(pw.running(self.name))

    def test_a_slow_page_still_counts_as_open(self):
        self.assertEqual(self.start("slow", wait=6.0), {"ok": True})                  # the window is there: hers to finish
        self.assertTrue(pw.running(self.name))
        self.assertFalse(pw.running(self.name + pw.READY))
        self.assertTrue(pw.close(self.name, wait=20)["ok"])

    def test_pywebview_missing_after_all(self):
        answer = self.start("missing")
        self.assertEqual((answer["ok"], answer["code"]), (False, "failed"))
        self.assertIn("needs pywebview", answer["reason"])
        self.assertNotIn(ME, pw._installed)                                           # asked again next time

    def test_opened_and_closed_again(self):
        answer = self.start("gone")
        self.assertEqual(answer, {"ok": False, "code": "closed", "reason": "Her desktop window opened and closed again."})

    def test_a_crash_says_its_last_line(self):
        answer = self.start("crash")
        self.assertEqual((answer["ok"], answer["code"]), (False, "failed"))
        self.assertEqual(answer["reason"], "RuntimeError: no window today")

    def test_never_opening_is_stopped_and_reported(self):
        killed = []
        real = pw._kill_tree

        def kill(pid):
            killed.append(pid)
            real(pid)

        with mock.patch.object(pw, "_kill_tree", kill):
            answer = self.start("never", wait=1.0)
        self.assertEqual(answer, {"ok": False, "code": "failed",
                                  "reason": "Her desktop window did not open in time. See logs/pet.log."})
        self.assertEqual(len(killed), 1)
        self.assertIsNone(pw._child)

    def test_before_anything_starts(self):
        with mock.patch.object(pw.subprocess, "Popen", side_effect=AssertionError("nothing may start")):
            missing = pw.start("http://localhost:53000", python=self.tmp / "nope.exe", script=self.stub,
                               name=self.name, log=self.log)
            self.assertEqual(missing["code"], "no_python")
            pw._installed[ME] = (False, time.monotonic())
            self.assertEqual(self.start("opens")["code"], "not_installed")
            pw._installed[ME] = (True, time.monotonic())
            handle, _ = pet.claim_instance(self.name)                                 # her window is open already
            self.addCleanup(pet.release, [handle])
            self.assertEqual(self.start("opens", power=True), {"ok": True, "already": True})


class Pip:
    """subprocess.run as install() uses it: the "is pywebview there?" question, and pip."""

    def __init__(self, there, code=0, output=b"", error=None):
        self.there, self.code, self.output, self.error, self.commands = list(there), code, output, error, []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        if command[1] == "-c":
            return SimpleNamespace(returncode=0 if self.there.pop(0) else 3)
        if self.error is not None:
            raise self.error
        kwargs["stdout"].write(self.output)
        return SimpleNamespace(returncode=self.code)


@unittest.skipUnless(WINDOWS, "her desktop window is Windows-only")
class InstallTests(unittest.TestCase):
    """The page's "Install and open": pip into the Python that opens her window (pip itself is played)."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory(prefix="pet-install-", ignore_cleanup_errors=True)
        self.addCleanup(folder.cleanup)
        self.log = Path(folder.name) / "logs" / "pet-install.log"
        pw.forget_pywebview()
        self.addCleanup(pw.forget_pywebview)

    def install(self, pip, python=ME):
        with mock.patch.object(pw.subprocess, "run", pip):
            return pw.install(python=python, log=self.log)

    def failed(self, pip):
        answer = self.install(pip)
        self.assertEqual((answer["ok"], answer["code"]), (False, "install_failed"))
        return answer["reason"]

    def test_one_small_install(self):
        pip = Pip([False, True], output=b"Successfully installed pywebview-6.2.1\n")
        self.assertEqual(self.install(pip), {"ok": True})
        self.assertEqual(pip.commands[1], [ME, "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
                                           "-r", str(ROOT / "brain" / "requirements-pet.txt")])
        self.assertIn("Successfully installed", self.log.read_text("utf-8"))
        self.assertEqual(pw._installed[ME][0], True)                     # kept: the button opens her at once

    def test_nothing_to_do(self):
        pip = Pip([True])
        self.assertEqual(self.install(pip), {"ok": True, "already": True})
        self.assertEqual(len(pip.commands), 1)                           # pip did not run

    def test_pip_says_why(self):
        output = b"Collecting pywebview\nERROR: No matching distribution found for pywebview\nnote: see above\n"
        self.assertEqual(self.failed(Pip([False], code=1, output=output)),
                         "ERROR: No matching distribution found for pywebview "
                         "The full output is in logs/pet-install.log.")
        self.assertEqual(self.failed(Pip([False], code=1, output=b"no network\n")),
                         "no network The full output is in logs/pet-install.log.")
        self.assertEqual(self.failed(Pip([False], code=7)),
                         "pip stopped with code 7. The full output is in logs/pet-install.log.")

    def test_installed_is_only_true_when_her_python_can_load_it(self):
        self.assertEqual(self.failed(Pip([False, False], output=b"Successfully installed something\n")),
                         "pip finished, but that Python still cannot load pywebview. See logs/pet-install.log.")

    def test_too_slow_or_not_startable(self):
        self.assertEqual(self.failed(Pip([False], error=subprocess.TimeoutExpired("pip", 600))),
                         "The install took too long and was stopped. See logs/pet-install.log.")
        self.assertIn("The install could not start", self.failed(Pip([False], error=OSError("access is denied"))))

    def test_no_python_no_install(self):
        pip = Pip([])
        answer = self.install(pip, python=self.log.parent / "nope.exe")
        self.assertEqual((answer["ok"], answer["code"]), (False, "no_python"))
        self.assertEqual(pip.commands, [])


# ── speech/api.py: the routes and the socket, lifted out of the source (the server itself needs a GPU stack) ─────
SOURCE = ROOT / "speech" / "api.py"
TREE = ast.parse(SOURCE.read_text(encoding="utf-8"))
ROUTES = {"_pet_guard", "_pet_json", "_pet_session_gone", "pet_state", "pet_open", "pet_close", "pet_install",
          "ws_dialog"}
STATE = {"_pet_busy", "_PET_BUSY"}


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Ask:
    """A request as the Use page sends it (ui/common.js postAction), from this PC unless told otherwise."""

    def __init__(self, action=None, body=b"{}", client="127.0.0.1", host="localhost:53000", **headers):
        self.client = SimpleNamespace(host=client)
        self.url = SimpleNamespace(scheme="http", netloc=host)
        self.headers = {"host": host}
        if action:
            self.headers.update({"origin": "http://" + host, "content-type": "application/json",
                                 "x-build-f-action": action})
        self.headers.update({key.replace("_", "-"): value for key, value in headers.items()})
        self.data = body if isinstance(body, bytes) else json.dumps(body).encode()

    async def body(self):
        return self.data


class Window:
    """speech/pet_window.py as the routes use it. Who may ask is the real rule; nothing opens."""

    is_local = staticmethod(pw.is_local)

    def __init__(self, ns):
        self.ns, self.calls, self.open, self.installed = ns, [], False, True
        self.start_answer, self.close_answer = {"ok": True}, None

    def pet_python(self):
        return Path("python.exe")

    def has_pywebview(self, python):
        return self.installed

    def running(self):
        return self.open

    def start(self, base, power=False, mic=False):
        self.calls.append(("start", base, power, mic, self.ns["_dialog_active"]))
        self.open = bool(self.start_answer.get("ok"))
        return dict(self.start_answer)

    def close(self):
        self.calls.append(("close",))
        if self.close_answer is not None:
            return dict(self.close_answer)
        was, self.open = self.open, False
        return {"ok": True, "was_running": was}

    def install(self):
        self.calls.append(("install",))
        self.installed = True
        return {"ok": True}


class Link:
    _connected = True

    async def connect(self):
        pass

    async def disconnect(self):
        pass


class Dialog:
    SAMPLE_RATE, FRAME_SAMPLES = 16000, 512

    def __init__(self, ws):
        self.ws, self.hane, self.tts, self._pending_partial = ws, Link(), Link(), None


class Socket:
    """A dialog socket that connects, looks who holds her session, and leaves."""

    def __init__(self, ns=None, **query):
        self.ns, self.query_params, self.closed, self.messages, self.held_by = ns, query, None, [], None

    async def accept(self):
        pass

    async def close(self, code=1000):
        self.closed = code

    async def send_json(self, data):
        self.messages.append(data)

    async def receive(self):
        self.held_by = self.ns["_dialog_owner"] if self.ns["_dialog_active"] else None
        return {"type": "websocket.disconnect"}


class RouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = {"AMIKA_CHAT_URL": "http://localhost:53010"}
        self.ns = {"asyncio": asyncio, "json": json, "HTTPException": HTTPException, "Request": Ask,
                   "WebSocket": Socket, "DialogSession": Dialog, "_dialog_sessions": set(),
                   "os": SimpleNamespace(name="nt", getenv=lambda key, default=None: self.env.get(key, default)),
                   "_wipe_in_progress": False, "_dialog_active": False, "_dialog_owner": None,
                   "WebSocketDisconnect": type("WebSocketDisconnect", (Exception,), {}),
                   "logger": SimpleNamespace(exception=lambda *a: None)}
        self.window = self.ns["pet_window"] = Window(self.ns)
        nodes = [copy.deepcopy(n) for n in TREE.body
                 if (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ROUTES)
                 or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) in STATE)]
        for node in nodes:
            node.decorator_list = []
        exec(compile(ast.Module(nodes, type_ignores=[]), "<pet routes>", "exec"), self.ns)
        self.assertTrue(ROUTES | STATE <= set(self.ns))

    def session(self, owner):
        self.ns["_dialog_active"], self.ns["_dialog_owner"] = owner is not None, owner

    def ends_soon(self):
        async def end():
            await asyncio.sleep(0.25)
            self.session(None)
        return asyncio.create_task(end())

    async def refused(self, route, request, status, words):
        with self.assertRaises(HTTPException) as caught:
            await self.ns[route](request)
        self.assertEqual(caught.exception.status_code, status)
        self.assertIn(words, caught.exception.detail)
        self.assertEqual(self.window.calls, [])

    async def test_what_the_button_needs(self):
        state = await self.ns["pet_state"](Ask())
        self.assertEqual(state, {"supported": True, "local": True, "running": False, "installed": True,
                                 "session": None})
        self.window.open, self.window.installed = True, False
        self.session("pet")
        state = await self.ns["pet_state"](Ask(host="127.0.0.1:53000"))
        self.assertEqual(state, {"supported": True, "local": True, "running": True, "installed": False,
                                 "session": "pet"})

    async def test_no_button_on_another_device(self):
        self.window.open = True
        for ask in (Ask(client="192.168.1.20", host="192.168.1.5:53000"), Ask(x_forwarded_for="100.64.0.2"),
                    Ask(tailscale_user_login="someone@example.com"), Ask(host="evil.example:53000")):
            self.assertEqual(await self.ns["pet_state"](ask), {"supported": True, "local": False})
        self.ns["os"].name = "posix"
        self.assertEqual(await self.ns["pet_state"](Ask()), {"supported": False, "local": True})

    async def test_only_her_own_page_on_this_pc_may_ask(self):
        for route, action in (("pet_open", "open-pet"), ("pet_close", "close-pet"), ("pet_install", "install-pet")):
            await self.refused(route, Ask(action, client="192.168.1.20"), 403, "this PC itself")
            await self.refused(route, Ask(action, x_forwarded_for="100.64.0.2"), 403, "this PC itself")
            await self.refused(route, Ask(action, host="evil.example:53000"), 403, "this PC itself")
            await self.refused(route, Ask("wipe-memory"), 403, "Use the OpenAmika page")
            await self.refused(route, Ask(action, origin="http://evil.example"), 403, "Use the OpenAmika page")
            await self.refused(route, Ask(action, origin="http://127.0.0.1:53000"), 403, "Use the OpenAmika page")
            await self.refused(route, Ask(action, content_type="text/plain"), 415, "JSON")
            await self.refused(route, Ask(action, body=b"x" * 1025), 400, "too large")
            await self.refused(route, Ask(action, body=b"{"), 400, "Invalid JSON")
            await self.refused(route, Ask(action, body=b"[]"), 400, "JSON object")
        self.assertFalse(self.ns["_pet_busy"])

    async def test_open_hands_over_what_was_on(self):
        self.assertEqual(await self.ns["pet_open"](Ask("open-pet", {"power": True, "mic": True})), {"ok": True})
        self.assertEqual(self.window.calls, [("start", "http://localhost:53010", True, True, False)])
        self.assertFalse(self.ns["_pet_busy"])

    async def test_only_a_plain_true_switches_anything_on(self):
        for body in ({"power": 1, "mic": "yes"}, {"power": "true"}, {}, b""):
            self.window.open = False
            await self.ns["pet_open"](Ask("open-pet", body))
            self.assertEqual(self.window.calls.pop()[2:4], (False, False), body)

    async def test_her_address_comes_from_the_launcher_never_from_the_request(self):
        for env, base in (({"AMIKA_CHAT_URL": "http://localhost:53010"}, "http://localhost:53010"),
                          ({"YUMEHA_PORT": "53020"}, "http://localhost:53020"), ({}, "http://localhost:53000")):
            self.env.clear()
            self.env.update(env)
            self.window.open = False
            await self.ns["pet_open"](Ask("open-pet", host="127.0.0.1:53999"))
            self.assertEqual(self.window.calls.pop()[1], base)

    async def test_the_tab_lets_her_go_first(self):
        self.session("page")                                             # the tab's socket is on its way out
        task = self.ends_soon()
        self.assertEqual(await self.ns["pet_open"](Ask("open-pet", {"power": True})), {"ok": True})
        await task
        # her session was free when the window opened: her page there can take it at once
        self.assertEqual(self.window.calls, [("start", "http://localhost:53010", True, False, False)])

    async def test_an_open_window_is_not_opened_twice(self):
        self.window.open = True
        self.assertEqual(await self.ns["pet_open"](Ask("open-pet")), {"ok": True, "already": True})
        self.assertEqual(self.window.calls, [])

    async def test_an_idle_window_is_replaced_when_she_was_talking_in_the_tab(self):
        self.window.open = True
        self.assertEqual(await self.ns["pet_open"](Ask("open-pet", {"power": True})), {"ok": True})
        self.assertEqual([call[0] for call in self.window.calls], ["close", "start"])
        del self.window.calls[:]
        self.window.open, self.window.close_answer = True, {"ok": False, "reason": "Her window did not close."}
        self.assertEqual(await self.ns["pet_open"](Ask("open-pet", {"power": True})),
                         {"ok": False, "code": "failed", "reason": "Her window did not close."})
        self.assertEqual(self.window.calls, [("close",)])

    async def test_not_during_a_service_control_or_another_pet_action(self):
        self.ns["_wipe_in_progress"] = True
        for route, action in (("pet_open", "open-pet"), ("pet_close", "close-pet")):
            answer = await self.ns[route](Ask(action))
            self.assertEqual((answer["ok"], answer["code"], bool(answer["reason"])), (False, "busy", True))
        self.ns["_wipe_in_progress"], self.ns["_pet_busy"] = False, True
        for route, action in (("pet_open", "open-pet"), ("pet_close", "close-pet"), ("pet_install", "install-pet")):
            self.assertEqual((await self.ns[route](Ask(action)))["code"], "busy")
        self.assertEqual(self.window.calls, [])
        self.assertTrue(self.ns["_pet_busy"])                            # the action that runs still holds it

    async def test_a_failure_lets_the_next_action_through(self):
        def broken(base, power=False, mic=False):
            raise OSError("no window today")

        self.window.start = broken
        with self.assertRaises(OSError):
            await self.ns["pet_open"](Ask("open-pet"))
        self.assertFalse(self.ns["_pet_busy"])

    async def test_bring_her_back(self):
        self.window.open = True
        self.session("pet")                                              # she is talking in her window
        task = self.ends_soon()
        answer = await self.ns["pet_close"](Ask("close-pet"))
        self.assertEqual(answer, {"ok": True, "was_running": True, "had_session": True})
        self.assertFalse(self.ns["_dialog_active"])                      # the answer waited: the tab can connect at once
        await task

    async def test_bring_her_back_when_she_was_not_talking_there(self):
        self.window.open = True
        self.session("page")                                             # another tab talks with her: not the window's
        self.assertEqual(await self.ns["pet_close"](Ask("close-pet")),
                         {"ok": True, "was_running": True, "had_session": False})
        self.window.close_answer = {"ok": False, "reason": "Her window did not close."}
        self.assertEqual(await self.ns["pet_close"](Ask("close-pet")),
                         {"ok": False, "reason": "Her window did not close.", "had_session": False})
        self.assertFalse(self.ns["_pet_busy"])

    async def test_the_one_small_install(self):
        self.window.installed = False
        self.ns["_wipe_in_progress"] = True                              # not her session's business: it may run
        self.assertEqual(await self.ns["pet_install"](Ask("install-pet")), {"ok": True})
        self.assertEqual(self.window.calls, [("install",)])
        self.assertFalse(self.ns["_pet_busy"])

    async def test_the_session_knows_who_holds_it(self):
        for query, owner in (({"pet": "1"}, "pet"), ({}, "page")):
            socket = Socket(self.ns, **query)
            await self.ns["ws_dialog"](socket)
            self.assertEqual(socket.held_by, owner)
            self.assertEqual(socket.messages[0]["type"], "ready")
            self.assertEqual((self.ns["_dialog_active"], self.ns["_dialog_owner"]), (False, None))

    async def test_a_tab_is_told_that_she_is_in_her_window(self):
        self.session("pet")
        tab = Socket(self.ns)
        await self.ns["ws_dialog"](tab)
        self.assertEqual(tab.closed, 1008)
        self.assertEqual(tab.messages[0]["code"], "pet_session")         # ui/use.js: "Amika is on your desktop"
        self.assertIn("Bring her back here", tab.messages[0]["message"])
        self.assertEqual((self.ns["_dialog_active"], self.ns["_dialog_owner"]), (True, "pet"))   # hers to keep

    async def test_everyone_else_gets_the_old_answer(self):
        for owner, query in (("page", {}), ("page", {"pet": "1"}), ("pet", {"pet": "1"})):
            self.session(owner)
            socket = Socket(self.ns, **query)
            await self.ns["ws_dialog"](socket)
            self.assertEqual(socket.closed, 1008)
            self.assertNotIn("code", socket.messages[0])
            self.assertIn("another tab", socket.messages[0]["message"])
            self.assertEqual(self.ns["_dialog_owner"], owner)


class ShippedTests(unittest.TestCase):
    """The page, the server and her window name the same things (a renamed id or action breaks the button)."""

    @staticmethod
    def text(*parts):
        return ROOT.joinpath(*parts).read_text(encoding="utf-8")

    def test_the_use_page_has_the_button_and_the_way_back(self):
        html = self.text("ui", "use.html")
        for needle in ('id="petBtn"', 'aria-label="Desktop pet"', "<span>Desktop pet</span>", 'id="petAway"',
                       'id="petBackBtn"', "Bring her back here", 'id="petSetup"', 'id="petInstallBtn"',
                       "Install and open", 'id="petInstallNo"'):
            self.assertIn(needle, html)

    def test_the_page_and_the_server_use_the_same_actions(self):
        script, server = self.text("ui", "use.js"), self.text("speech", "api.py")
        for path, action in (("/api/pet/open", "open-pet"), ("/api/pet/close", "close-pet"),
                             ("/api/pet/install", "install-pet")):
            self.assertIn(f'postAction("{path}", "{action}"', script)
            self.assertIn(f'@app.post("{path}")', server)
            self.assertIn(f'_pet_guard(request, "{action}")', server)
        self.assertIn('getJSON("/api/pet")', script)
        self.assertIn('@app.get("/api/pet")', server)

    def test_the_session_goes_with_her_and_not_in_the_address(self):
        script, server, window = self.text("ui", "use.js"), self.text("speech", "api.py"), self.text("pet.py")
        self.assertIn('"/ws/dialog" + (PET ? "?pet=1" : "")', script)     # her window says who it is
        self.assertIn("window.pywebview.api.handover()", script)          # and asks what to switch on
        self.assertIn('msg.code === "pet_session" && !PET', script)       # a tab learns where she went
        self.assertIn('"code": "pet_session"', server)
        for flag in ("'--close-with'", "'--power'", "'--mic'"):
            self.assertIn(flag, window)
        for name in ("power", "mic"):                                     # never in the page address
            self.assertNotIn(f"&{name}=", script)
            self.assertNotIn(f"?{name}=", script)

    def test_the_tab_rests_while_she_is_out(self):
        script, engine, css = self.text("ui", "use.js"), self.text("ui", "live2d-engine.js"), \
            self.text("ui", "openamika.css")
        self.assertIn("avatar.setPaused(out)", script)
        self.assertIn("function setPaused(on) {", engine)
        self.assertIn("setPaused,", engine)
        self.assertIn(".pet-away-note {", css)
        self.assertIn(".stage-area.pet-away canvas", css)
        self.assertIn("html.pet .pet-away-note", css)                     # her own window never shows the note

    def test_the_helper_is_plain_python(self):
        """pet_window.py runs inside the speech server: no new package for the server just for the button."""
        tree = ast.parse(self.text("speech", "pet_window.py"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add((node.module or "").split(".")[0])
        self.assertLessEqual(names, set(sys.stdlib_module_names), names - set(sys.stdlib_module_names))


if __name__ == "__main__":
    unittest.main()
