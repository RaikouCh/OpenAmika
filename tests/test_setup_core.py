"""scripts/setup_core.py: the decisions it makes and the files it writes, without installing anything. Offline."""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("setup_core", ROOT / "scripts" / "setup_core.py")
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


@pytest.fixture()
def checkout(tmp_path, monkeypatch):
    """setup_core.py looking at an empty checkout (the shipped templates only)."""
    for rel in ("settings.example.json", ".env.example"):
        shutil.copyfile(ROOT / rel, tmp_path / rel)
    (tmp_path / "brain").mkdir()
    monkeypatch.setattr(core, "ROOT", tmp_path)
    monkeypatch.setattr(core, "ENVS", tmp_path / "envs")
    core.ROWS.clear()
    return tmp_path


def rows():
    return {name: (mark.strip(), detail) for mark, name, detail in core.ROWS}


def test_gpu_line_parsing():
    assert core.parse_gpu("NVIDIA GeForce RTX 5080, 16303\n") == ("NVIDIA GeForce RTX 5080", 16303)
    assert core.parse_gpu("NVIDIA GeForce RTX 3060, 12288\nNVIDIA GeForce GT 710, 2048\n") == ("NVIDIA GeForce RTX 3060", 12288)
    assert core.parse_gpu("") is None and core.parse_gpu("No devices were found") is None


def test_her_eyes_need_a_16_gb_card_unless_asked():
    big, small = ("RTX 5080", 16303), ("RTX 4070", 12282)
    assert core.vision_wanted("auto", "cuda", big)[0] is True
    on, why = core.vision_wanted("auto", "cuda", small)
    assert on is False and "--vision on" in why and "12 GB" in why
    assert core.vision_wanted("auto", "cpu", None)[0] is False
    assert core.vision_wanted("on", "cuda", small)[0] is True
    assert core.vision_wanted("off", "cuda", big) == (False, "skipped (--vision off)")


def test_settings_point_at_the_new_environments(checkout):
    cfg = core.settings_from_example("cuda", vision_on=True)
    venv = ["Scripts", "python.exe"] if core.IS_WIN else ["bin", "python"]
    assert Path(cfg["brain_python"]).parts == ("envs", "brain", *venv)
    assert Path(cfg["embedder"]["python"]).parts == ("envs", "embed", *venv)
    assert cfg["vision"]["enabled"] is True and cfg["speech_device"] == "cuda:0"
    cpu = core.settings_from_example("cpu", vision_on=False)
    assert cpu["speech_device"] == "cpu" and cpu["embedder"]["device"] == "cpu" and cpu["embedder"]["dtype"] == "fp32"
    assert cpu["vision"]["enabled"] is False
    assert cpu["services"]["tts"]["command"][0].endswith("python.exe")        # her voice server block is kept


def test_a_conda_environment_from_the_old_readme_is_used_as_it_is(checkout):
    if not core.IS_WIN:
        pytest.skip("conda -p layout is a Windows path")
    (checkout / "envs" / "brain").mkdir(parents=True)
    (checkout / "envs" / "brain" / "python.exe").write_bytes(b"")
    assert core.env_python(checkout / "envs" / "brain") == checkout / "envs" / "brain" / "python.exe"
    assert core.settings_from_example("cuda", False)["brain_python"] == str(Path("envs/brain/python.exe"))


def make_envs(checkout, *names):
    for name in names:
        exe = core.env_python(checkout / "envs" / name)
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b"")


def test_settings_json_is_created_once_and_never_changed(checkout):
    args = core.argparse.Namespace(check=False)
    core.ensure_settings("cuda", True, args)
    path = checkout / "settings.json"
    assert json.loads(path.read_text("utf-8"))["vision"]["enabled"] is True
    assert rows()["settings.json"][0] == "OK" and "created" in rows()["settings.json"][1]
    core.ROWS.clear()
    core.ensure_settings("cuda", True, args)          # its environments are not made yet: their own rows say why
    mark, detail = rows()["settings.json"]
    assert mark == "--" and "not made yet" in detail and "see the speech recognition row" in detail
    make_envs(checkout, "brain", "speech", "embed", "vision")
    before = path.read_bytes()
    core.ROWS.clear()
    core.ensure_settings("cpu", True, args)                                   # other choices: the file stays as it is
    assert path.read_bytes() == before and rows()["settings.json"] == ("OK", "existing, not changed (its interpreters exist)")


def test_an_interpreter_outside_envs_that_is_gone_names_the_environment_to_use(checkout):
    cfg = core.settings_from_example("cuda", False)
    cfg["speech_python"] = str(checkout / "elsewhere" / "python.exe")
    (checkout / "settings.json").write_text(json.dumps(cfg), "utf-8")
    make_envs(checkout, "brain", "speech", "embed")
    with pytest.raises(core.SetupError) as caught:
        core.ensure_settings("cuda", False, core.argparse.Namespace(check=False))
    message = str(caught.value)
    assert "as speech_python, which does not exist" in message
    assert f"point speech_python at {core.rel(core.env_python(checkout / 'envs' / 'speech'))}" in message


def test_a_rerun_after_an_interrupted_first_run_ends_with_ok_settings(checkout, monkeypatch):
    """The first run made envs\\brain and settings.json, then stopped (Ctrl+C in the speech environment's torch
    download); the re-run makes the rest and its summary has no !! row for settings.json."""
    made = []

    def make_env(key, base_py, device, args):               # stands in for venv + torch + pip
        folder = core.ENV_SPECS[key][0]
        make_envs(checkout, folder)
        made.append(folder)
        exe = core.env_python(core.ENVS / folder)
        core.row("OK ", core.ROW_NAMES[key], f"{core.rel(exe)} (existing)")
        return exe

    monkeypatch.setattr(core, "ensure_env", make_env)
    monkeypatch.setattr(core.base, "find_base_python", lambda explicit: (["py", "-3.11"], (3, 11, 9)))
    monkeypatch.setattr(core, "gpu_info", lambda: ("NVIDIA GeForce RTX 5080", 16303))
    monkeypatch.setattr(core, "ensure_speech_model", lambda args: core.row("OK ", "speech model", "verified"))
    monkeypatch.setattr(core, "ensure_hf_model", lambda label, vpy, folder, repo, *rest: core.row("OK ", label, repo))
    make_envs(checkout, "brain")
    (checkout / "settings.json").write_text(json.dumps(core.settings_from_example("cuda", True)), "utf-8")
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = core.main([])
    got = rows()
    assert rc == 0, out.getvalue()
    assert made == ["brain", "speech", "embed", "vision"]
    assert got["settings.json"][0] == "OK" and not any(mark == "!!" for mark, _ in got.values())
    assert got["vision model"] == ("OK", "Qwen/Qwen3-VL-2B-Instruct")
    assert list(got)[-2:] == ["settings.json", "brain/.env"]                 # written after the environments
    assert (".\\Start_OpenAmika.bat" if core.IS_WIN else "launch.py") in out.getvalue()      # PowerShell needs the .\


def test_models_named_in_settings_json_are_the_ones_fetched(checkout):
    assert core.chosen_models() == ("BAAI/bge-m3", "qwen3-vl-2b")
    cfg = core.settings_from_example("cuda", True)
    cfg["embedder"]["model"], cfg["vision"]["model"] = "intfloat/multilingual-e5-large", "smolvlm2-500m"
    (checkout / "settings.json").write_text(json.dumps(cfg), "utf-8")
    assert core.chosen_models() == ("intfloat/multilingual-e5-large", "smolvlm2-500m")
    assert core.vision_repo("smolvlm2-500m") == "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
    with pytest.raises(core.SetupError, match="does not know"):
        core.vision_repo("no-such-model")


def test_a_damaged_package_is_installed_again_but_never_torch_or_a_too_long_path():
    found = {"bad": {"cv2": "ImportError: DLL load failed while importing cv2: The specified module could not be found.",
                     "torch": "OSError: [WinError 126] fbgemm.dll", "PIL": "ImportError: cannot import name '_imaging'",
                     "resampy": "ImportError: DLL load failed while importing _box: The filename or extension is too long."},
             "broken": {"cv2": ["opencv-python==4.12.0.88"], "torch": ["torch==2.10.0+cu128"], "PIL": ["pillow==12.0.0"],
                        "resampy": ["resampy==0.4.3"]}}
    assert core.damaged_dists(found) == ["opencv-python==4.12.0.88", "pillow==12.0.0"]
    assert core.damaged_dists({"bad": {"funasr": "ModuleNotFoundError"}, "broken": {}}) == []


def test_brain_env_file_is_copied_and_a_missing_key_is_informational(checkout):
    args = core.argparse.Namespace(check=False)
    core.ensure_env_file(args)
    assert (checkout / "brain" / ".env").read_text("utf-8") == (checkout / ".env.example").read_text("utf-8")
    mark, detail = rows()["brain/.env"]
    assert mark == "--" and "no OpenRouter key yet" in detail and "wizard" in detail
    (checkout / "brain" / ".env").write_text("OPENROUTER_API_KEY=placeholder-for-the-test-1234\n", "utf-8")
    core.ROWS.clear()
    core.ensure_env_file(args)
    assert rows()["brain/.env"] == ("OK", "OpenRouter key set (...1234)")


def test_onedrive_detection_uses_windows_own_variables(tmp_path, monkeypatch):
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        monkeypatch.delenv(var, raising=False)
    named_like_it = tmp_path / "C--Users-x-OneDrive-Desktop" / "OpenAmika"
    named_like_it.mkdir(parents=True)
    assert core.synced_by_onedrive(named_like_it) is False                    # the word alone is not a sync
    monkeypatch.setenv("OneDrive", str(tmp_path / "C--Users-x-OneDrive-Desktop"))
    assert core.synced_by_onedrive(named_like_it) is True


def test_check_on_an_empty_checkout_lists_everything_and_changes_nothing(checkout, monkeypatch):
    monkeypatch.setattr(core, "gpu_info", lambda: ("NVIDIA GeForce RTX 5080", 16303))
    monkeypatch.setattr(core, "hf_cached", lambda repo: None)
    monkeypatch.setattr(core, "ensure_speech_model", lambda args: (_ for _ in ()).throw(
        core.SetupError("speech/models/ is not complete: run this script without --check")))
    with contextlib.redirect_stdout(io.StringIO()) as out:
        rc = core.main(["--check"])
    got = rows()
    assert rc == 1
    assert got["brain"][0] == "!!" and "not created yet" in got["brain"][1]
    assert got["settings.json"][0] == "!!" and got["speech model"][0] == "!!"
    assert got["memory model"][0] == "--" and "skipped: needs memory (embedder)" in got["memory model"][1]
    assert got["vision (her eyes)"] == ("--", "not installed yet: this script installs them on this GPU")
    assert "Not ready: run this script without --check" in out.getvalue()
    assert sorted(p.name for p in checkout.iterdir()) == [".env.example", "brain", "settings.example.json"]


def test_the_windows_entry_point_parses_and_needs_no_bom():
    ps1 = ROOT / "scripts" / "setup_windows.ps1"
    raw = ps1.read_bytes()
    assert raw.isascii(), "non-ASCII text in a .ps1 needs a UTF-8 BOM for Windows PowerShell 5.1"
    assert b"setup_core.py" in raw and b"@args" in raw
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("no PowerShell here")
    script = ("$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:OA_PS1, [ref]$null, [ref]$e); "
              "if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }")
    import os
    import subprocess
    p = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                       env={**os.environ, "OA_PS1": str(ps1)}, timeout=120)
    assert p.returncode == 0, p.stdout + p.stderr


def test_the_windows_entry_point_takes_3_11_then_3_12_and_passes_the_callers_folder_on():
    text = (ROOT / "scripts" / "setup_windows.ps1").read_text("ascii")
    assert "foreach ($want in @('3.11', '3.12'))" in text
    assert "$env:OPENAMIKA_CALLER_DIR = $callerDir" in text and "$env:OPENAMIKA_CALLER_SHELL" in text
    assert text.index("$callerDir = (Get-Location)") < text.index("Set-Location -LiteralPath $root")
    assert "numpy 1.26.4" in text


# ---- the window it runs in: the ZIP's nested folder, another folder, another shell ---------------------------------
def test_the_inner_folder_of_a_github_zip_is_recognised():
    for name in ("OpenAmika-main", "OpenAmika-1.0.0", "openamika-MAIN", "OpenAmika-v1.2"):
        inner = Path("C:/Users/me/Downloads") / name / name
        assert core.zip_outer(inner) == inner.parent, name
    assert core.zip_outer(Path("C:/OpenAmika")) is None
    assert core.zip_outer(Path("C:/Users/me/Downloads/OpenAmika-main")) is None          # unpacked "here": one level
    assert core.zip_outer(Path("D:/OpenAmika/OpenAmika")) is None                        # a clone inside a clone's name


def test_the_cd_line_suits_the_shell():
    root = Path("D:/Tools/OpenAmika")
    assert core.cd_command(root, "powershell") == f'cd "{root}"'
    assert core.cd_command(root, "cmd") == f'cd /d "{root}"'                             # cmd changes the drive with /d
    assert core.cd_command(root, "bash") == 'cd "/d/Tools/OpenAmika"'


def test_caller_shell_comes_from_the_windows_entry_point_or_git_bash(monkeypatch):
    for var in ("OPENAMIKA_CALLER_SHELL", "MSYSTEM"):
        monkeypatch.delenv(var, raising=False)
    assert core.caller_shell() == "powershell"
    monkeypatch.setenv("OPENAMIKA_CALLER_SHELL", "cmd.exe")
    assert core.caller_shell() == "cmd"
    monkeypatch.setenv("OPENAMIKA_CALLER_SHELL", "powershell.exe")
    monkeypatch.setenv("MSYSTEM", "MINGW64")
    assert core.caller_shell() == "bash"


def test_a_window_outside_her_folder_gets_the_exact_cd_line(tmp_path):
    outer = tmp_path / "OpenAmika-main"
    inner = outer / "OpenAmika-main"
    inner.mkdir(parents=True)
    notes, cd = core.folder_notes(inner, inner, "powershell")
    assert cd == f'cd "{inner}"' and notes == []                  # in the inner folder: fine, cd shown as a reminder
    notes, cd = core.folder_notes(inner, outer, "powershell")
    assert cd == f'cd "{inner}"' and "outer folder of the ZIP" in notes[0] and cd in notes[0]
    system32 = tmp_path / "Windows" / "System32"
    system32.mkdir(parents=True)
    notes, cd = core.folder_notes(inner, system32, "cmd")
    assert cd == f'cd /d "{inner}"' and str(system32) in notes[0]
    clone = tmp_path / "OpenAmika"
    clone.mkdir()
    assert core.folder_notes(clone, clone, "powershell") == ([], "")
    notes, _ = core.folder_notes(clone, clone, "bash")
    assert any("Git Bash" in n for n in notes)


def test_the_summary_ends_with_the_cd_line_when_the_window_is_elsewhere(checkout, monkeypatch, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setenv("OPENAMIKA_CALLER_DIR", str(elsewhere))
    monkeypatch.delenv("MSYSTEM", raising=False)
    monkeypatch.setenv("OPENAMIKA_CALLER_SHELL", "powershell.exe")
    monkeypatch.setattr(core, "gpu_info", lambda: None)
    monkeypatch.setattr(core, "hf_cached", lambda repo: None)
    monkeypatch.setattr(core, "ensure_speech_model", lambda args: None)
    with contextlib.redirect_stdout(io.StringIO()) as out:
        core.main(["--check"])
    text = out.getvalue()
    assert f'cd "{checkout}"' in text and str(elsewhere) in text


# ---- the Hugging Face token ---------------------------------------------------------------------------------------
@pytest.fixture()
def no_token(tmp_path, monkeypatch):
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HF_HUB_DISABLE_IMPLICIT_TOKEN"):
        monkeypatch.setenv(var, "-")        # recorded first, so the HF_TOKEN the code sets is removed afterwards
        monkeypatch.delenv(var)
    saved = tmp_path / "hf" / "token"
    monkeypatch.setenv("HF_TOKEN_PATH", str(saved))
    return saved


def ns(**kw):
    import argparse
    return argparse.Namespace(**{"check": False, "no_token_prompt": False, **kw})


def test_a_token_already_set_is_used_without_asking(no_token, monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "hf_" + "x" * 30)
    mark, note = core.ask_hf_token(ns(), ask=lambda prompt: pytest.fail("asked"))
    assert mark.strip() == "OK" and "HF_TOKEN" in note and "x" * 30 not in note


def test_no_console_or_check_never_asks(no_token, monkeypatch):
    monkeypatch.setattr(core, "console_input", lambda: False)
    mark, note = core.ask_hf_token(ns(), ask=lambda prompt: pytest.fail("asked"))
    assert mark.strip() == "--" and "huggingface.co/settings/tokens" in note
    monkeypatch.setattr(core, "console_input", lambda: True)
    assert core.ask_hf_token(ns(check=True), ask=lambda prompt: pytest.fail("asked"))[0].strip() == "--"
    assert core.ask_hf_token(ns(no_token_prompt=True), ask=lambda prompt: pytest.fail("asked"))[0].strip() == "--"


def test_a_pasted_token_is_checked_set_and_saved_like_hf_auth_login(no_token, monkeypatch):
    monkeypatch.setattr(core, "console_input", lambda: True)
    token = "hf_" + "AbCd" * 8 + "wxyz"
    with contextlib.redirect_stdout(io.StringIO()) as out:
        mark, note = core.ask_hf_token(ns(), ask=lambda prompt: f"  {token} \n", check=lambda t: t == token)
    assert mark.strip() == "OK" and "...wxyz" in note and token not in note and token not in out.getvalue()
    assert "huggingface.co/settings/tokens" in out.getvalue()
    assert core.os.environ["HF_TOKEN"] == token
    assert no_token.read_text("utf-8") == token
    assert core.base.hf_token(None)[0] == token                      # setup_tts.py finds it from now on
    del core.os.environ["HF_TOKEN"]
    assert core.base.hf_token(None) == (token, "`hf auth login`")    # also in a new window (the saved file)


def test_enter_skips_and_a_wrong_token_is_not_kept(no_token, monkeypatch):
    monkeypatch.setattr(core, "console_input", lambda: True)
    with contextlib.redirect_stdout(io.StringIO()):
        assert core.ask_hf_token(ns(), ask=lambda prompt: "")[0].strip() == "--"
        mark, note = core.ask_hf_token(ns(), ask=lambda prompt: "hf_" + "z" * 30, check=lambda t: False)
        assert mark.strip() == "--" and "did not accept" in note
        mark, note = core.ask_hf_token(ns(), ask=lambda prompt: "my password", check=lambda t: True)
        assert mark.strip() == "--" and "start with hf_" in note
    assert not no_token.exists() and "HF_TOKEN" not in core.os.environ


# ---- Python 3.11 / 3.12 / 3.13 ------------------------------------------------------------------------------------
def test_python_3_11_and_3_12_are_allowed_3_13_is_not():
    ok = core.base.ok_version
    assert ok((3, 11, 9)) and ok((3, 12, 7))
    assert not ok((3, 10, 14)) and not ok((3, 13, 1)) and not ok((3, 14, 0)) and not ok(None)
    assert "numpy 1.26.4" in core.PYTHON_NEEDED and "3.13" in core.PYTHON_NEEDED


def test_the_base_python_prefers_3_11_then_takes_3_12_and_refuses_3_13(monkeypatch):
    base = core.base
    monkeypatch.setattr(base.shutil, "which", lambda name: None)
    def versions(table):
        monkeypatch.setattr(base, "py_version", lambda cmd: table.get(" ".join(cmd[1:]) if cmd[0] == "py" else "self"))
    versions({"self": (3, 12, 7), "-3.11": (3, 11, 9), "-3.12": (3, 12, 7)})
    assert base.find_base_python(None) == (["py", "-3.11"], (3, 11, 9)) if base.IS_WIN else True
    versions({"self": (3, 12, 7)})
    with contextlib.redirect_stdout(io.StringIO()) as out:
        cmd, v = base.find_base_python(None)
    assert v == (3, 12, 7) and "only 3.11 is tested" in out.getvalue()
    versions({"self": (3, 13, 1)})
    with pytest.raises(core.SetupError, match="numpy"):
        base.find_base_python(None)


def test_check_says_when_an_update_changed_a_requirements_file(checkout):
    import argparse
    py = core.env_python(core.ENVS / "brain")
    py.parent.mkdir(parents=True)
    py.write_bytes(b"")
    (core.ENVS / "brain" / "openamika-requirements.sha256").write_text("an older requirements file", "utf-8")
    (checkout / "brain" / "requirements.txt").write_text("flask==3.0.0\n", "utf-8")
    with pytest.raises(core.SetupError, match="changed since it was installed"):
        core.ensure_env("brain", [], "cpu", argparse.Namespace(check=True, reinstall=False))


# ---- the Hugging Face models: their weights fetched here, resumable ----------------------------------------------
def test_the_weight_files_are_the_ones_a_loader_reads():
    def f(name, size=10):
        return {"rfilename": name, "size": size, "lfs": {"sha256": "ab" * 32, "size": size}}
    bin_only = [f("pytorch_model.bin"), f("onnx/model.onnx_data"), {"rfilename": "config.json", "size": 5}]
    assert [w[0] for w in core.weight_files(bin_only)] == ["pytorch_model.bin"]
    both = [f("model.safetensors"), f("pytorch_model.bin"), f("tokenizer.json")]
    assert [w[0] for w in core.weight_files(both)] == ["model.safetensors"]
    sharded = [f("model-00001-of-00002.safetensors"), f("model-00002-of-00002.safetensors")]
    assert len(core.weight_files(sharded)) == 2
    assert core.weight_files([f("onnx/model.onnx")]) == []


def test_an_interrupted_weight_download_continues_where_it_stopped(tmp_path, monkeypatch):
    import hashlib
    import http.server
    import threading
    import urllib.parse
    data = bytes(range(256)) * 4096                      # 1 MB of weights
    sha = hashlib.sha256(data).hexdigest()
    commit = "c0ffee" * 6 + "abcd"
    ranges = []

    class Hub(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/models/org/model/revision/main":
                body = json.dumps({"sha": commit, "siblings": [
                    {"rfilename": "config.json", "size": 2},
                    {"rfilename": "model.safetensors", "size": len(data), "lfs": {"sha256": sha, "size": len(data)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            assert path == f"/org/model/resolve/{commit}/model.safetensors", path
            start = 0
            if self.headers.get("Range"):
                start = int(self.headers["Range"].split("=")[1].split("-")[0])
                ranges.append(start)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
            else:
                self.send_response(200)
            self.send_header("Content-Length", str(len(data) - start))
            self.end_headers()
            self.wfile.write(data[start:])

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Hub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(core.base, "HF", f"http://127.0.0.1:{server.server_address[1]}")
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    monkeypatch.setenv("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    target = tmp_path / "hub" / "models--org--model" / "snapshots" / commit / "model.safetensors"
    target.parent.mkdir(parents=True)
    (target.parent / "model.safetensors.part").write_bytes(data[:300_000])      # an earlier run stopped here
    env = tmp_path / "envs" / "vision"
    env.mkdir(parents=True)
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            note = core.prefetch_weights("org/model", env)
            again = core.prefetch_weights("org/model", env)
    finally:
        server.shutdown()
    assert target.read_bytes() == data and ranges == [300_000]
    assert "continuing at" in out.getvalue()
    assert "downloaded and checked" in note and "in place and checked" in again and ranges == [300_000]


def test_progress_lines_show_speed_and_what_is_left():
    line = core.base.progress_line("model.safetensors", 1_000_000_000, 4_000_000_000, 10e6)
    assert "1,000 / 4,000 MB (25%)" in line and "10.0 MB/s" in line and "3.0 GB left" in line and "about 5 min" in line
    assert "50 KB/s" in core.base.progress_line("x", 1, 10_000_000, 50e3)
    assert core.base.progress_line("x", 5_000_000, 0, 2e6) == "x: 5 MB so far, 2.0 MB/s"
