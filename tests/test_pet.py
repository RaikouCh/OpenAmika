"""Her desktop pet window: pet.py's plain helpers (address, geometry, zoom), launch.py --pet (the pre-flight line, the
pet window row, who stops it) and what ships with it.

Offline; imports pet.py and launch.py without running them, and never opens a window (pywebview is not needed).
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pet = _load("openamika_pet", ROOT / "pet.py")
launch = _load("openamika_launch_for_pet", ROOT / "launch.py")


class AddressTests(unittest.TestCase):
    def test_chat_url_from_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("﻿" + json.dumps({"chat_port": 53010}), "utf-8")      # a BOM, as Notepad saves it
            self.assertEqual(pet.chat_url(path), "http://localhost:53010")
            path.write_text("{not json", "utf-8")
            self.assertEqual(pet.chat_url(path), "http://localhost:53000")
            self.assertEqual(pet.chat_url(Path(tmp) / "missing.json"), "http://localhost:53000")

    def test_pet_url(self):
        self.assertEqual(pet.pet_url("http://localhost:53000/"), "http://localhost:53000/use?pet=1")

    def test_the_microphone_goes_to_her_own_page_only(self):
        base = "http://localhost:53000"
        self.assertTrue(pet.same_origin("http://localhost:53000/use?pet=1", base))
        self.assertFalse(pet.same_origin("http://localhost:53001/use", base))
        self.assertFalse(pet.same_origin("https://localhost:53000/use", base))
        self.assertFalse(pet.same_origin("http://127.0.0.1:53000/use", base))
        self.assertFalse(pet.same_origin("http://evil.example/use", base))
        self.assertFalse(pet.same_origin("not a url", base))


class GeometryTests(unittest.TestCase):
    def test_round_trip_and_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pet-window" / "window.json"
            self.assertIsNone(pet.load_geometry(path))
            pet.save_geometry(path, {"x": -1200, "y": 40, "width": 320, "height": 560})
            self.assertEqual(pet.load_geometry(path), {"x": -1200, "y": 40, "width": 320, "height": 560})
            for bad in ({"x": 1, "y": 2, "width": 20, "height": 560}, {"x": 1, "y": 2, "width": 320},
                        {"x": "a", "y": 2, "width": 320, "height": 560}):
                path.write_text(json.dumps(bad), "utf-8")
                self.assertIsNone(pet.load_geometry(path), bad)

    def test_saver_writes_after_moves_and_on_flush(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "window.json"
            saver = pet.GeometrySaver(path, {"x": None, "y": None, "width": 320, "height": 560}, delay=60)
            saver.resized(330, 570)
            saver.flush()
            self.assertFalse(path.exists())              # no position yet (the window was centred by pywebview)
            saver.moved(100, 200)
            saver.flush()
            saver.timer.cancel()
            self.assertEqual(json.loads(path.read_text("utf-8")), {"x": 100, "y": 200, "width": 330, "height": 570})

    def test_zoom_keeps_her_feet_where_they_are(self):
        left, top, width, height = pet.zoomed((1000, 400, 320, 560), 1.25, (160, 240), 1400)
        self.assertEqual((width, height), (400, 700))
        self.assertEqual(top + height, 400 + 560)                    # same bottom edge
        self.assertEqual(left + width // 2, 1000 + 320 // 2)         # same centre line

    def test_zoom_limits(self):
        self.assertEqual(pet.zoomed((0, 0, 320, 560), 10, (160, 240), 1120)[3], 1120)    # the screen's height
        small = pet.zoomed((0, 0, 320, 560), 0.01, (160, 240), 1120)
        self.assertEqual(small[2:], (160, 280))                    # the narrower limit wins, the aspect stays


class LaunchPetTests(unittest.TestCase):
    def test_pet_check_names_the_install_command(self):
        with mock.patch.object(launch.importlib.util, "find_spec", return_value=None), \
                mock.patch.object(launch.os, "name", "nt"):
            level, detail = launch.pet_check()
        self.assertEqual(level, "err")
        self.assertIn("-m pip install -r " + os.path.join("brain", "requirements-pet.txt"), detail)
        self.assertIn("browser", detail)
        with mock.patch.object(launch.importlib.util, "find_spec", return_value=object()), \
                mock.patch.object(launch.os, "name", "nt"):
            self.assertEqual(launch.pet_check()[0], "ok")

    def test_the_row_follows_the_window(self):
        window = launch.PetWindow("http://localhost:53000")
        self.assertEqual(window.cmd[-3:], [str(ROOT / "pet.py"), "--url", "http://localhost:53000"])
        self.assertEqual(window.cmd[0], sys.executable)
        self.assertEqual(window.light(0)[1], "off")                 # before speech is up: waiting, not a failure
        window.proc, window.state, window.started_by_me = SimpleNamespace(poll=lambda: None), "starting", True
        window.poll()
        self.assertEqual(window.state, "up")
        window.proc = SimpleNamespace(poll=lambda: 0, returncode=0)        # closed with its button
        window.poll()
        self.assertEqual(window.state, "off")
        self.assertIn("pet.py", window.detail)
        window.proc, window.state = SimpleNamespace(poll=lambda: 3, returncode=3), "up"
        window.poll()
        self.assertEqual(window.state, "failed")

    def test_page_opener_opens_the_pet_instead_of_the_browser(self):
        opened = []
        page = launch.PageOpener("http://localhost:53000", SimpleNamespace(state="up"), opener=opened.append)
        self.assertTrue(page.check())
        self.assertEqual(opened, ["http://localhost:53000"])

    def test_stopped_with_the_rest(self):
        self.assertIn("pet.py", launch.CORE_SCRIPTS)                # grace cleanup of an earlier instance
        stop = (ROOT / "Stop_OpenAmika.ps1").read_text("utf-8-sig")
        self.assertIn("(Join-Path $root 'pet.py')", stop)


class ShippedTests(unittest.TestCase):
    def test_requirements_are_optional_and_windows_only(self):
        lines = [ln for ln in (ROOT / "brain" / "requirements-pet.txt").read_text("utf-8").splitlines()
                 if ln and not ln.startswith("#")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("pywebview"))
        self.assertIn('sys_platform == "win32"', lines[0])
        self.assertNotIn("pywebview", (ROOT / "brain" / "requirements.txt").read_text("utf-8"))

    def test_start_script_passes_pet(self):
        bat = (ROOT / "Start_OpenAmika_Pet.bat").read_text("utf-8")
        self.assertIn('call "%~dp0Start_OpenAmika.bat" --pet', bat)

    def test_the_page_turns_into_the_pet_before_its_first_paint(self):
        html = (ROOT / "ui" / "use.html").read_text("utf-8")
        head = html[:html.index("</head>")]
        self.assertIn('classList.add("pet")', head)
        use = (ROOT / "ui" / "use.js").read_text("utf-8")
        for needle in ('const PET = document.documentElement.classList.contains("pet")', "fixed: PET",
                       "if (!PET) firstRun()", 'host("zoom"', "pywebview-drag-region"):
            self.assertIn(needle, use)
        js = pet.PetApi("http://localhost:53000")
        for name in ("zoom", "full_page", "close"):                  # what use.js calls on window.pywebview.api
            self.assertTrue(callable(getattr(js, name)))
        self.assertFalse([n for n in vars(js) if not n.startswith("_")])   # nothing else is exposed to the page


if __name__ == "__main__":
    unittest.main()
