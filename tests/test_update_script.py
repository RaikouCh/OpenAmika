"""Update_OpenAmika.bat (scripts/update_openamika.ps1) keeps her memory: what it backs up, the order of its steps, and
that nothing in the setups ever writes into her memory folders. Static checks, plus a PowerShell parse where one is
installed; nothing is run against this checkout."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "update_openamika.ps1"
BAT = ROOT / "Update_OpenAmika.bat"


def test_the_bat_runs_the_script_and_keeps_its_window_open():
    bat = BAT.read_text("ascii")
    assert 'scripts\\update_openamika.ps1"' in bat and "-ExecutionPolicy Bypass" in bat
    assert bat.rstrip().endswith("pause")


def test_the_script_is_ascii_and_parses():
    raw = PS1.read_bytes()
    assert raw.isascii(), "non-ASCII text in a .ps1 needs a UTF-8 BOM for Windows PowerShell 5.1"
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("no PowerShell here")
    script = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:OA_PS1, [ref]$null, [ref]$e); "
              "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }")
    p = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                       env={**os.environ, "OA_PS1": str(PS1)}, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def test_it_backs_up_her_memory_and_every_settings_file_before_git_runs():
    text = PS1.read_text("ascii")
    for item in ("'memory_f'", "'brain\\memories'", "'settings.json'", "'brain\\.env'", "'config\\seed.json'",
                 "'config\\ollama.json'", "'config\\voice_map.json'", "'config\\tools.json'", "'config\\messengers.json'"):
        assert item in text, item
    code = text[text.index("$root = Split-Path"):]          # after the header comment, which names the steps too
    order = [code.index(marker) for marker in ("She is running", "update-$stamp.zip", "stash push", "pull --ff-only",
                                               "stash pop", "setup_windows.ps1') --check", "setup_tts.py') --verify")]
    assert order == sorted(order)
    assert "checkout --theirs" in text                 # a conflict keeps the person's own version


def test_her_memory_and_the_backups_are_never_committed():
    ignored = (ROOT / ".gitignore").read_text("utf-8").splitlines()
    for entry in ("memory_f/", "brain/memories/", "backups/", "settings.json", "config/seed.json", "config/ollama.json",
                  "config/voice_map.json", "config/tools.json", "config/messengers.json"):
        assert entry in ignored, entry


def test_the_setups_never_touch_her_memory():
    for script in ("scripts/setup_core.py", "scripts/setup_tts.py", "scripts/download_sensevoice.py",
                   "scripts/setup_windows.ps1"):
        text = (ROOT / script).read_text("utf-8")
        assert not re.search(r"memory_f|brain[\\/]+memories", text), script
