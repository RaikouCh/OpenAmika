"""Update_OpenAmika.bat (scripts/update_openamika.ps1) keeps her memory: what it backs up, the order of its steps, and
that nothing in the setups ever writes into her memory folders. Static checks, a PowerShell parse where one is
installed, and the update itself in a throwaway clone under pytest's temp folder (Windows with git); nothing is run
against this checkout."""
import json
import os
import re
import shutil
import subprocess
import zipfile
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


# README "No Update_OpenAmika.bat in her folder?": the first update of a clone from before the script existed.
FIRST_UPDATE = ("git fetch origin",
                r"git show origin/main:scripts/update_openamika.ps1 > scripts\update_once.ps1",
                r"powershell -ExecutionPolicy Bypass -File scripts\update_once.ps1")
BUILD_F = '{\n  "user_name": "",\n  "city": "",\n  "language": "en",\n  "auto_open": true%s\n}\n'
MEMORY, SETTINGS = b'{"turns": 412}', b'{"ui_port": 53000}'


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


@pytest.fixture
def older_clone(tmp_path):
    """`her`: a clone from before the update script existed, with a memory and a settings file. Its origin then gets
    this checkout's script and .bat, one more line in a file the Setup page writes, and a setup that only answers
    "all in place" (the real one would install into the clone)."""
    if os.name != "nt" or not shutil.which("powershell") or not shutil.which("git"):
        pytest.skip("needs Windows PowerShell and git")
    origin, her = tmp_path / "origin", tmp_path / "her"
    (origin / "config").mkdir(parents=True)
    (origin / "scripts").mkdir()
    (origin / ".gitignore").write_text("memory_f/\nsettings.json\n", "ascii")
    (origin / "config" / "build_f.json").write_text(BUILD_F % "", "ascii")
    (origin / "scripts" / "setup_windows.ps1").write_text("exit 0\n", "ascii")
    git(tmp_path, "init", "-q", "-b", "main", "origin")
    git(origin, "add", "-A")
    git(origin, "commit", "-q", "-m", "before the update script")
    git(tmp_path, "clone", "-q", "origin", "her")
    shutil.copy(PS1, origin / "scripts" / PS1.name)
    shutil.copy(BAT, origin / BAT.name)
    (origin / ".gitignore").write_text("memory_f/\nsettings.json\nbackups/\n", "ascii")
    (origin / "config" / "build_f.json").write_text(BUILD_F % ',\n  "silence_remarks": "normal"', "ascii")
    git(origin, "add", "-A")
    git(origin, "commit", "-q", "-m", "the update")
    (her / "memory_f").mkdir()
    (her / "memory_f" / "ledger.json").write_bytes(MEMORY)
    (her / "settings.json").write_bytes(SETTINGS)
    return her


def first_update(her):
    p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                        "; ".join(FIRST_UPDATE) + "; exit $LASTEXITCODE"], cwd=her, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    assert p.returncode == 0 and "Updated. Start her" in p.stdout, p.stdout + p.stderr
    assert (her / "Update_OpenAmika.bat").is_file() and (her / "scripts" / PS1.name).is_file()
    assert (her / "memory_f" / "ledger.json").read_bytes() == MEMORY
    assert (her / "settings.json").read_bytes() == SETTINGS
    return p.stdout


def test_every_readme_gives_the_first_update_lines_that_are_run_here():
    for readme in ("README.md", "README.zh-CN.md", "README.ja.md", "README_IF_YOU_ARE_AI_AGENT.md"):
        text = (ROOT / readme).read_text("utf-8")
        for line in FIRST_UPDATE:
            assert line in text, (readme, line)


def test_a_copy_of_the_script_updates_a_clone_from_before_it_and_keeps_her_memory(older_clone):
    her = older_clone
    (her / "config" / "build_f.json").write_text(BUILD_F.replace('"user_name": ""', '"user_name": "Rin"') % "", "ascii")
    first_update(her)
    build_f = json.loads((her / "config" / "build_f.json").read_text("ascii"))
    assert build_f["user_name"] == "Rin" and build_f["silence_remarks"] == "normal"      # her line and the update's
    (backup,) = (her / "backups").glob("update-*.zip")
    with zipfile.ZipFile(backup) as z:
        assert {"memory_f/ledger.json", "settings.json", "config/build_f.json"} <= set(z.namelist())
        assert z.read("memory_f/ledger.json") == MEMORY
        assert json.loads(z.read("config/build_f.json"))["user_name"] == "Rin"           # taken before git ran
    assert git(her, "stash", "list") == ""


def test_a_file_both_sides_changed_keeps_the_persons_version(older_clone):
    her = older_clone
    edited = BUILD_F.replace('"auto_open": true', '"auto_open": false') % ""             # the line the update changes
    (her / "config" / "build_f.json").write_text(edited, "ascii")
    out = first_update(her)
    assert "Your version is kept:" in out and "config/build_f.json" in out
    assert json.loads((her / "config" / "build_f.json").read_text("ascii")) == json.loads(edited)   # no markers
    assert git(her, "status", "--porcelain", "--untracked-files=no").split() == ["M", "config/build_f.json"]
    assert "OpenAmika update" in git(her, "stash", "list")                    # her edit stays in the stash list as well
