#!/usr/bin/env python3
# Copyright (c) 2026 MekaHime Inc.
# SPDX-License-Identifier: MIT
"""Set up OpenAmika's core on this PC: her brain, her ears (speech recognition), her memory (the embedder) and her eyes
(the camera), with the models they load, settings.json and brain/.env. Her voice and her Live2D model come next, from
scripts/setup_tts.py. Windows runs this through scripts/setup_windows.ps1, which finds Python 3.11 first.

    powershell -ExecutionPolicy Bypass -File scripts\\setup_windows.ps1   # Windows (finds Python 3.11, runs this)
    py -3.11 scripts\\setup_core.py                                      # the same, by hand
    ... --cpu            no NVIDIA GPU: CPU builds (speech recognition and memory run on the CPU, slower)
    ... --vision on|off  her eyes (the camera): auto (default) installs them when the GPU has 16 GB or more
    ... --check          report what is installed and what is missing; change nothing
    ... --reinstall      run every pip step again
    ... --no-token-prompt  do not ask for a Hugging Face token

First it asks for an optional Hugging Face token (Enter skips; https://huggingface.co/settings/tokens makes a free
one): without one Hugging Face throttles the model downloads, with one they run at full speed. A token pasted there is
kept where `hf auth login` keeps it (HF_TOKEN_PATH, else "token" in HF_HOME, by default ~/.cache/huggingface), so the
next runs and scripts/setup_tts.py use it too; one already set (HF_TOKEN, or a saved login) is used without asking.

What it makes, all inside this folder and all git-ignored:

    envs/brain     Python 3.11 venv + brain/requirements.txt: the brain and the launcher (no GPU)
    envs/speech    + torch/torchaudio (CUDA 12.8) + speech/requirements.txt: speech recognition, every web page, the
                   Discord/Telegram service
    envs/embed     + torch + brain/requirements-embedder.txt: her memory's embedder (BAAI/bge-m3)
    envs/vision    + torch + vision/requirements.txt: her eyes (Qwen3-VL-2B); only with --vision on / a 16 GB GPU
    speech/models/ SenseVoiceSmall (~940 MB) by scripts/download_sensevoice.py, every file pinned by SHA-256
    the Hugging Face cache (HF_HOME, by default ~/.cache/huggingface): BAAI/bge-m3 (~2.3 GB), and
                   Qwen/Qwen3-VL-2B-Instruct (~4.3 GB) with her eyes, so the first start does not wait for them
    settings.json  from settings.example.json, pointing at these environments (an existing one is never changed);
                   written after the environments, so a run stopped half-way never leaves it naming missing ones
    brain/.env     from .env.example: your OpenRouter key goes there, or into the first-run wizard on the Use page

Every step prints what it does; the summary at the end has one row per part (OK, -- skipped or informational, !!
failed, each with its fix) and the exit code is 1 if any row is !! (130 after Ctrl-C). Running it again is the fix
for almost everything: what is installed and working is checked and skipped (pip runs again only when a requirements
file changed, or with --reinstall; a package that is installed but no longer imports is installed again), and the
downloads resume (the big weight files of the two Hugging Face models are fetched here first, through a .part file
that a re-run continues, with the speed and the size left on screen). An environment folder made with
`conda create -p envs\\<name>` (the earlier README) is used as it is. Python 3.11 is the tested one; 3.12 works too
(every pinned package has wheels for it). 3.13 and newer cannot run her voice server: it pins numpy 1.26.4
(GPT-SoVITS needs numpy<2), which has no wheels for them. Only the standard library is needed to run this; it shares
its download, venv and summary helpers with setup_tts.py.

The window it runs in matters for the commands after it, which are relative to this folder: the summary prints the
exact `cd` line when that window is elsewhere (the outer folder of GitHub's ZIP, OpenAmika-main\\OpenAmika-main, for
one) and says so when it is Git Bash, whose paths are not Windows paths.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import setup_tts as base  # noqa: E402  (shared helpers: run, pip, Steps, the summary rows)
from setup_tts import ROWS, IS_MAC, IS_WIN, SetupError, log, long_folder_warning, row, too_long_hint  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENVS = ROOT / "envs"
# One torch for the three core environments (the voice server pins its own in setup_tts.py): the build the speech
# environment was tested with (funasr 1.3.1, silero-vad 6.2); the embedder and vision run on it too. pip's cache
# downloads the wheel once for all three. torchaudio and torchvision are the releases paired with that torch (vision
# needs torchvision: transformers' Qwen3-VL processors and qwen-vl-utils import it).
TORCH_VERSION = "2.10.0"
TORCH_PINS = {"torch": TORCH_VERSION, "torchaudio": "2.10.0", "torchvision": "0.25.0"}
TORCH_INDEX = {"cuda": "https://download.pytorch.org/whl/cu128", "cpu": "https://download.pytorch.org/whl/cpu"}
TORCH_LOCAL = {"cuda": "+cu128", "cpu": "+cpu", "mac": ""}
VISION_MIN_MIB = 15000        # "auto" gives her eyes to cards of 16 GB and more: next to her ears, memory and voice
                              # (~6 GB with their CUDA contexts) the vision model needs ~4.3 GB more
EMBED_MODEL_DEFAULT = "BAAI/bge-m3"
VISION_MODEL_DEFAULT = "qwen3-vl-2b"
VLM_SERVICE = Path(__file__).resolve().parent.parent / "vision" / "vlm_service.py"   # its MODELS: key -> repository
# settings.json interpreter -> (the envs\ folder this script makes for it, the summary row of that environment)
SETTINGS_ENVS = {"brain_python": ("brain", "brain"), "speech_python": ("speech", "speech recognition"),
                 "embedder.python": ("embed", "memory (embedder)"), "vision.python": ("vision", "vision (her eyes)")}
TORCH_DISTS = ("torch", "torchaudio", "torchvision")   # installed from the PyTorch index only (ensure_torch)
HF_TOKEN_PAGE = "https://huggingface.co/settings/tokens"
# GitHub's "Download ZIP" and the release zips unpack into a folder of that name inside a folder of that name:
# OpenAmika-main\OpenAmika-main, OpenAmika-1.0.0\OpenAmika-1.0.0
ZIP_FOLDER = re.compile(r"OpenAmika-(main|master|v?\d+(\.\d+)*[\w.+-]*)", re.IGNORECASE)
PYTHON_NEEDED = ("OpenAmika needs Python 3.11 (3.12 works too): install 3.11 from "
                 "https://www.python.org/downloads/release/python-3119/ (tick \"Add python.exe to PATH\"), open a new "
                 "window and run this again. Python 3.13 and newer cannot run her voice server: it needs numpy 1.26.4 "
                 "(GPT-SoVITS pins numpy<2), which has no wheels for them")

# name, folder under envs/, requirements, torch packages, modules that must import
ENV_SPECS = {
    "brain": ("brain", "brain/requirements.txt", (),
              ["flask", "flask_cors", "flask_socketio", "socketio", "requests", "dotenv", "numpy", "mcp", "google.genai",
               "tzdata"]),
    "speech": ("speech", "speech/requirements.txt", ("torch", "torchaudio"),
               ["torch", "torchaudio", "soundfile", "numpy", "fastapi", "uvicorn", "funasr", "modelscope", "silero_vad",
                "socketio", "aiohttp", "multipart"]),
    "memory": ("embed", "brain/requirements-embedder.txt", ("torch",),
               ["torch", "sentence_transformers", "transformers", "huggingface_hub"]),
    "vision": ("vision", "vision/requirements.txt", ("torch", "torchvision"),
               ["torch", "torchvision", "transformers", "accelerate", "qwen_vl_utils", "cv2", "PIL", "numpy", "fastapi",
                "uvicorn", "websocket"]),
}
ROW_NAMES = {"brain": "brain", "speech": "speech recognition", "memory": "memory (embedder)", "vision": "vision (her eyes)"}

PROBE = r"""
import importlib, json, sys
out, bad, broken = {}, {}, {}
for name in sys.argv[1:]:
    try:
        mod = importlib.import_module(name)
        out[name] = str(getattr(mod, "__version__", "ok"))
    except Exception as e:
        bad[name] = (type(e).__name__ + ": " + str(e))[:200]
if bad:
    # installed but not importable (a damaged install that pip calls satisfied): which distributions hold the module,
    # as name==version, so exactly those files can be put in place again
    try:
        import importlib.metadata as md
        for dist in md.distributions():
            files = {str(f).replace("\\", "/") for f in (dist.files or [])}
            for name in bad:
                stem = name.replace(".", "/")
                if stem + "/__init__.py" in files or any(f.startswith(stem + ".") and "/" not in f[len(stem):]
                                                         for f in files):
                    broken.setdefault(name, []).append(dist.metadata["Name"] + "==" + dist.version)
    except Exception:
        pass
if "torch" in out:
    import torch
    out["_cuda"] = torch.version.cuda or ""
    out["_cuda_ok"] = bool(torch.cuda.is_available())
    out["_gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
print("PROBE " + json.dumps({"ok": out, "bad": bad, "broken": broken}))
"""


# ---- small helpers ----------------------------------------------------------------------------------------------
def rel(path: Path) -> str:
    """A path as settings.json and the messages write it: relative to this folder when it is inside it."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def env_python(folder: Path) -> Path:
    """The interpreter of an environment folder: a venv's Scripts\\python.exe (bin/python elsewhere), or the
    python.exe at the top of a `conda create -p` environment."""
    cands = [folder / "Scripts" / "python.exe", folder / "python.exe"] if IS_WIN else [folder / "bin" / "python"]
    return next((c for c in cands if c.is_file()), cands[0])


def gpu_info() -> Optional[tuple[str, int]]:
    """(name, total MiB) of the first NVIDIA GPU, from nvidia-smi; None without one (or without its driver)."""
    exe = shutil.which("nvidia-smi")
    if not exe and IS_WIN:
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        exe = str(cand) if cand.exists() else None
    if not exe:
        return None
    try:
        p = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True,
                           text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_gpu(p.stdout) if p.returncode == 0 else None


def parse_gpu(text: str) -> Optional[tuple[str, int]]:
    for line in text.splitlines():
        name, _, mib = line.rpartition(",")
        if name.strip() and mib.strip().isdigit():
            return name.strip(), int(mib.strip())
    return None


def vision_wanted(mode: str, device: str, gpu: Optional[tuple[str, int]]) -> tuple[bool, str]:
    """(install her eyes, why) for --vision auto|on|off."""
    if mode == "off":
        return False, "skipped (--vision off)"
    if mode == "on":
        return True, "--vision on" + ("" if device == "cuda" else " (on the CPU: very slow)")
    if device != "cuda" or gpu is None:
        return False, "skipped: no NVIDIA GPU (her eyes need about 4.3 GB of VRAM; --vision on installs them anyway)"
    if gpu[1] < VISION_MIN_MIB:
        return False, (f"skipped: {gpu[0]} has {gpu[1] / 1024:.0f} GB and her eyes need about 4.3 GB more next to her "
                       "ears, memory and voice (16 GB cards). --vision on installs them anyway; then set "
                       "\"vision\": {\"enabled\": true} in settings.json")
    return True, f"{gpu[0]} has {gpu[1] / 1024:.0f} GB"


def probe(vpy: Path, modules: list[str]) -> dict:
    try:
        p = subprocess.run([str(vpy), "-I", "-c", PROBE, *modules], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": {}, "bad": {"python": f"{type(e).__name__}: {e}"}}
    line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith("PROBE ")), "")
    if not line:
        return {"ok": {}, "bad": {"python": (p.stderr.strip().splitlines() or [f"exit code {p.returncode}"])[-1][:300]}}
    return json.loads(line[len("PROBE "):])


def damaged_dists(found: dict) -> list[str]:
    """name==version of the distributions whose modules are installed but do not import (damaged files that pip calls
    satisfied), except the torch family (ensure_torch reinstalls those from the PyTorch index) and except a Windows
    path that is too long, which reinstalling cannot fix."""
    out: list[str] = []
    for name, dists in (found.get("broken") or {}).items():
        if too_long_hint(found["bad"].get(name, "")):
            continue
        out += [d for d in dists if d.split("==")[0].lower() not in TORCH_DISTS and d not in out]
    return out


def torch_note(found: dict) -> str:
    if "torch" not in found["ok"]:
        return ""
    gpu = found["ok"].get("_gpu")
    return f"; torch {found['ok']['torch']}, " + (f"CUDA OK on {gpu}" if gpu else "CPU")


def digest(*files: Path) -> str:
    h = hashlib.sha256()
    for f in files:
        h.update(f.read_bytes() if f.is_file() else b"")
    return h.hexdigest()


def same_folder(a: Path, b: Path) -> bool:
    try:
        return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))
    except OSError:
        return os.path.normcase(str(a)) == os.path.normcase(str(b))


# ---- the window this runs in ------------------------------------------------------------------------------------
def zip_outer(root: Path) -> Optional[Path]:
    """The outer folder when root is the inner folder of an unpacked GitHub ZIP (...\\OpenAmika-main\\OpenAmika-main,
    ...\\OpenAmika-1.0.0\\OpenAmika-1.0.0), else None."""
    if ZIP_FOLDER.fullmatch(root.name) and root.parent.name.lower() == root.name.lower():
        return root.parent
    return None


def caller_dir() -> Path:
    """The folder of the window that started the setup: setup_windows.ps1 passes it in OPENAMIKA_CALLER_DIR (it
    changes into this folder before it runs Python), else the current folder."""
    given = os.environ.get("OPENAMIKA_CALLER_DIR", "").strip()
    return Path(given) if given else Path.cwd()


def caller_shell() -> str:
    """'cmd', 'bash' (Git Bash / MSYS) or 'powershell' (the default): which form of cd the summary prints.
    setup_windows.ps1 passes the name of the program that started it in OPENAMIKA_CALLER_SHELL."""
    given = os.environ.get("OPENAMIKA_CALLER_SHELL", "").strip().lower()
    if given.startswith("cmd"):
        return "cmd"
    if os.environ.get("MSYSTEM") or given in ("bash.exe", "sh.exe", "bash", "sh", "mintty.exe"):
        return "bash"
    return "powershell"


def cd_command(root: Path, shell: str) -> str:
    """The cd line that takes a window of that shell into root (cmd needs /d to change the drive as well)."""
    if shell == "cmd":
        return f'cd /d "{root}"'
    if shell == "bash":
        text = str(root).replace("\\", "/")
        if len(text) > 1 and text[1] == ":":
            text = "/" + text[0].lower() + text[2:]
        return f'cd "{text}"'
    return f'cd "{root}"'


def folder_notes(root: Path, caller: Path, shell: str) -> tuple[list[str], str]:
    """(notes, cd line) about the window that runs the setup. The next commands are relative to root, so a window
    elsewhere (the outer folder of the ZIP, C:\\Windows\\System32, ...) gets the exact cd line; so does the inner
    folder of a ZIP, a reminder of which of the two same-named folders is hers. Git Bash gets a note of its own: the
    next commands are written for PowerShell (or cmd)."""
    notes: list[str] = []
    outer = zip_outer(root)
    cd = ""
    if not same_folder(caller, root):
        cd = cd_command(root, shell)
        if outer is not None and same_folder(caller, outer):
            notes.append(f"Your window is in {outer}, the outer folder of the ZIP. OpenAmika is the folder of the same "
                         f"name inside it: run {cd} before the next commands.")
        else:
            notes.append(f"Your window is in {caller}, not in the OpenAmika folder: run {cd} before the next commands.")
    elif outer is not None:
        cd = cd_command(root, shell)
    if shell == "bash":
        notes.append("This window is Git Bash: run the next commands in PowerShell instead (in the OpenAmika folder, "
                     "right-click an empty spot and choose Open in Terminal).")
    return notes, cd


# ---- the Hugging Face token -------------------------------------------------------------------------------------
def hf_token_file() -> Path:
    """Where `hf auth login` keeps the token: HF_TOKEN_PATH, else "token" in HF_HOME (~/.cache/huggingface)."""
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return Path(os.environ.get("HF_TOKEN_PATH") or os.path.join(home, "token"))


def console_input() -> bool:
    """True when a person can answer in this window: stdin is a real console. A pipe, a file or the NUL device (an
    agent's terminal often has one, and Windows calls it a tty) is not, so the question never hangs an unattended run."""
    try:
        if sys.stdin is None or not sys.stdin.isatty():
            return False
    except (AttributeError, ValueError, OSError):
        return False
    if not IS_WIN:
        return True
    try:
        import ctypes
        import msvcrt
        mode = ctypes.c_uint32()
        handle = msvcrt.get_osfhandle(sys.stdin.fileno())
        return bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return False


def check_hf_token(token: str) -> Optional[bool]:
    """Does huggingface.co accept the token? True, False (HTTP 401/403), or None when it cannot be asked."""
    req = urllib.request.Request("https://huggingface.co/api/whoami-v2",
                                 headers={**base.UA, "Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        return False if e.code in (401, 403) else None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def ask_hf_token(args: argparse.Namespace, ask=None, check=None) -> tuple[str, str]:
    """(mark, note) for the summary. A token already set (HF_TOKEN, or a saved `hf auth login`) is used as it is.
    Otherwise, in a console, ask for one, optional (Enter skips). A pasted token is checked with huggingface.co, set
    as HF_TOKEN for this run (the download steps inherit it) and saved where `hf auth login` saves it, for the next
    runs and scripts/setup_tts.py. It is never printed (only its last four characters)."""
    token, where = base.hf_token(None)
    if token:
        return "OK ", f"from {where}: the model downloads run at full speed"
    if args.check or args.no_token_prompt or not console_input():
        return "-- ", (f"none (optional: Hugging Face may throttle the downloads without one; make a free Read token at "
                       f"{HF_TOKEN_PAGE} and set $env:HF_TOKEN = \"hf_...\" before the setup)")
    print("\n[setup] Optional: a free Hugging Face token makes the model downloads much faster (without one,\n"
          "        Hugging Face can slow them to about 50 KB/s). Make one at " + HF_TOKEN_PAGE + "\n"
          "        (Create new token, type Read), copy it, paste it here (right-click or Ctrl+V: it stays hidden)\n"
          "        and press Enter. Or just press Enter to go on without one.", flush=True)
    try:
        token = ((ask or getpass.getpass)("[setup] Hugging Face token (Enter skips): ") or "").strip()
    except EOFError:
        print(flush=True)
        token = ""
    if not token:
        return "-- ", "skipped (the downloads may be slow; run this again with a token if they crawl)"
    if not token.startswith("hf_") or len(token) < 20:
        return "-- ", "that was not a Hugging Face token (they start with hf_): going on without one"
    accepted = (check or check_hf_token)(token)
    if accepted is False:
        return "-- ", "Hugging Face did not accept that token (HTTP 401): going on without one"
    os.environ["HF_TOKEN"] = token
    saved = hf_token_file()
    try:
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_text(token, encoding="utf-8")
        kept = f"saved in {saved}, where `hf auth login` keeps it (delete that file to forget it)"
    except OSError as e:
        kept = f"used for this run only (it could not be saved in {saved}: {e})"
    return "OK ", (f"...{token[-4:]} {'accepted by Hugging Face' if accepted else 'set (Hugging Face did not answer the check)'}"
                   f"; {kept}")


def synced_by_onedrive(folder: Path) -> bool:
    """True when folder is inside a OneDrive folder (Windows names them in OneDrive / OneDriveConsumer /
    OneDriveCommercial)."""
    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        top = os.environ.get(var, "").strip()
        if top:
            try:
                folder.resolve().relative_to(Path(top).resolve())
                return True
            except (ValueError, OSError):
                pass
    return False


# ---- environments -----------------------------------------------------------------------------------------------
def make_env(folder: Path, base_py: list[str]) -> tuple[Path, str]:
    """An environment at folder (created, repaired or reused); returns (python, how)."""
    vpy = env_python(folder)
    if vpy.is_file():
        v = base.py_version([str(vpy)])
        if v is not None and not base.ok_version(v):
            raise SetupError(f"{rel(folder)} uses Python {'.'.join(map(str, v))}; OpenAmika needs {base.PY_RANGE}: "
                             f"delete the folder {rel(folder)} and run this script again")
        if v is not None and base.pip_works(vpy):
            kind = "conda environment" if (folder / "conda-meta").is_dir() else "existing"
            return vpy, f"Python {'.'.join(map(str, v))}, {kind}"
        if (folder / "conda-meta").is_dir():
            raise SetupError(f"{rel(folder)} is a conda environment whose Python does not start or has no pip: delete "
                             "the folder and run this script again (it makes a venv)")
        log(f"{rel(folder)} is incomplete; creating it again")
        clear = True
    else:
        clear = folder.is_dir() and any(folder.iterdir())
    folder.parent.mkdir(parents=True, exist_ok=True)
    base.run(base_py + ["-m", "venv", *(["--clear"] if clear else []), str(folder)])
    vpy = env_python(folder)
    if not base.pip_works(vpy):
        raise SetupError(f"{rel(folder)} was created without pip" +
                         (" (Debian/Ubuntu: sudo apt install python3.11-venv)" if sys.platform.startswith("linux") else ""))
    base.run([str(vpy), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-U", "pip", "wheel"])
    v = base.py_version([str(vpy)]) or (0, 0, 0)
    return vpy, f"Python {'.'.join(map(str, v))}, {'created again' if clear else 'created'}"


def ensure_torch(vpy: Path, folder: Path, packages: tuple[str, ...], device: str, reinstall: bool) -> Optional[Path]:
    """torch (and torchaudio / torchvision) at TORCH_PINS for this device, held by a constraints file; None when the
    environment needs no torch."""
    if not packages:
        return None
    want = {p: f"{TORCH_PINS[p]}{TORCH_LOCAL[device]}" for p in packages}
    found = probe(vpy, list(packages))
    have = found["ok"]
    good = all(have.get(p, "").split("+")[0] == TORCH_PINS[p] for p in packages)
    if device == "cuda":
        good = good and str(have.get("_cuda") or "").startswith("12.8")
    elif device == "cpu":
        good = good and not have.get("_cuda")
    damaged = [p for p in packages if p in found.get("broken", {}) and not too_long_hint(found["bad"].get(p, ""))]
    if not good or reinstall:
        log(f"installing {' + '.join(f'{p} {want[p]}' for p in packages)} into {rel(folder)} "
            f"({'CUDA 12.8' if device == 'cuda' else device}; about 3 GB, downloaded once for every environment)")
        idx = [] if device == "mac" else ["--index-url", TORCH_INDEX[device]]
        base.pip(vpy, *idx, *(f"{p}=={want[p]}" for p in packages))
        # installed but damaged, or --reinstall: pip calls the build satisfied, so put the same files in place again
        redo = list(dict.fromkeys(damaged + ([p for p in packages if p in have] if reinstall else [])))
        if redo:
            base.pip(vpy, *idx, "--force-reinstall", "--no-deps", *(f"{p}=={want[p]}" for p in redo))
    cons = folder / "openamika-constraints.txt"
    cons.write_text("".join(f"{p}=={want[p]}\n" for p in packages), encoding="utf-8")
    return cons


def ensure_env(key: str, base_py: list[str], device: str, args: argparse.Namespace) -> Path:
    """One environment: venv, torch, its requirements file (pip only when it changed), then its imports."""
    name, req_rel, torch_pkgs, modules = ENV_SPECS[key]
    folder = ENVS / name
    if args.check:
        vpy = env_python(folder)
        if not vpy.is_file():
            raise SetupError(f"{rel(folder)} is not created yet: run this script without --check")
        how = "existing"
    else:
        vpy, how = make_env(folder, base_py)
    req = ROOT / req_rel
    if args.check:      # the constraints file the last install wrote (torch pins), to compare the stamp with
        cons = folder / "openamika-constraints.txt" if torch_pkgs and (folder / "openamika-constraints.txt").is_file() else None
    else:
        cons = ensure_torch(vpy, folder, torch_pkgs, device, args.reinstall)
    stamp = folder / "openamika-requirements.sha256"
    want = digest(req, *([cons] if cons else []))
    fresh = stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == want
    if args.check and stamp.is_file() and not fresh:
        # an update (git pull) changed the requirements file since it was installed: the imports may still pass
        raise SetupError(f"{req_rel} changed since it was installed into {rel(folder)}: run this script without --check")
    found = probe(vpy, modules)
    if not args.check and (args.reinstall or not fresh or found["bad"]):
        log(f"installing {req_rel} into {rel(folder)}" + (" (torch stays pinned)" if cons else ""))
        base.pip(vpy, "-r", str(req), *(["-c", str(cons)] if cons else []))
        stamp.write_text(want, encoding="utf-8")
        found = probe(vpy, modules)
        how += f"; {req_rel} installed"
        redo = damaged_dists(found)
        if redo:
            log(f"installing {', '.join(redo)} into {rel(folder)} again: installed, but it does not import (damaged files)")
            base.pip(vpy, "--force-reinstall", "--no-deps", *redo, *(["-c", str(cons)] if cons else []))
            found = probe(vpy, modules)
            how += f"; {', '.join(d.split('==')[0] for d in redo)} installed again"
    if found["bad"]:
        names = ", ".join(f"{k} ({v})" for k, v in list(found["bad"].items())[:3])
        hint = too_long_hint(" ".join(found["bad"].values()))
        raise SetupError(f"{rel(vpy)}: these do not import: {names}. "
                         + (hint[0].upper() + hint[1:] if hint else "Run this script without --check" if args.check else
                            "Run this script again with --reinstall; if it repeats, see the pip output above"))
    if device == "cuda" and "torch" in torch_pkgs and not found["ok"].get("_cuda_ok"):
        raise SetupError(f"{rel(vpy)}: torch {found['ok'].get('torch')} does not see the GPU (CUDA): update the NVIDIA "
                         "driver (https://www.nvidia.com/drivers), then run this script again; or run it with --cpu")
    row("OK ", ROW_NAMES[key], f"{rel(vpy)} ({how}{torch_note(found)})")
    return vpy


# ---- models -----------------------------------------------------------------------------------------------------
def ensure_speech_model(args: argparse.Namespace) -> None:
    """SenseVoiceSmall into speech/models/ (scripts/download_sensevoice.py: pinned SHA-256, resumable)."""
    cmd = [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "download_sensevoice.py"), *(["--verify"] if args.check else [])]
    p = subprocess.run(cmd, capture_output=args.check, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise SetupError("speech/models/ is not complete" + (": run this script without --check" if args.check else
                         " (see the lines above): run this script again (finished files are kept), or download the files "
                         "by hand from https://www.modelscope.cn/models/iic/SenseVoiceSmall into speech/models/"))
    row("OK ", "speech model", "speech/models/ (SenseVoiceSmall, 6 files verified by SHA-256)")


def hub_cache() -> Path:
    """The Hugging Face hub cache: HF_HUB_CACHE, else "hub" in HF_HOME (by default ~/.cache/huggingface/hub)."""
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return Path(os.environ.get("HF_HUB_CACHE") or os.path.join(home, "hub"))


def hf_cached(repo: str) -> Optional[Path]:
    """The snapshot folder of a Hugging Face model in the local cache, or None (a plain file check)."""
    snaps = hub_cache() / f"models--{repo.replace('/', '--')}" / "snapshots"
    found = [s for s in snaps.glob("*") if (s / "config.json").is_file()] if snaps.is_dir() else []
    return found[0] if found else None


def hf_main_files(repo: str, token: Optional[str]) -> tuple[str, list[dict]]:
    """(commit, files) of the repository's main revision from the Hub API (a mirror's when HF_ENDPOINT names one):
    each file with its size and, for a large (LFS) file, its SHA-256."""
    url = f"{base.HF}/api/models/{repo}/revision/main?blobs=true"
    req = urllib.request.Request(url, headers=dict(base.UA))
    if token and base.token_goes_to(url):
        req.add_unredirected_header("Authorization", "Bearer " + token)
    with base.OPENER.open(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    return str(data["sha"]), list(data.get("siblings") or [])


def weight_files(files: list[dict]) -> list[tuple[str, int, str]]:
    """(name, size, sha256) of the weight files a transformers loader reads from the repository's top folder: its
    .safetensors files when it has any (transformers prefers them), else its pytorch_model*.bin."""
    top = [f for f in files if "/" not in str(f.get("rfilename", "")) and (f.get("lfs") or {}).get("sha256")]
    safe = [f for f in top if f["rfilename"].endswith(".safetensors")]
    pick = safe or [f for f in top if re.fullmatch(r"pytorch_model(-\d+-of-\d+)?\.bin", f["rfilename"])]
    return [(str(f["rfilename"]), int(f["lfs"]["size"]), str(f["lfs"]["sha256"])) for f in pick]


def prefetch_weights(repo: str, folder: Path) -> str:
    """Put the model's big weight files into the Hugging Face cache before its loader runs, where the loader looks
    first (models--<org>--<name>/snapshots/<commit>/<file>), through a .part file that a re-run continues, checked
    against the SHA-256 the Hub lists, with the speed and the size left on screen every 10 s. (huggingface_hub 1.x
    starts an interrupted file over from its first byte.) The loader then fetches only the small files. Returns a
    note, or '' when the Hub could not be asked (the loader downloads everything itself, as before)."""
    token = base.hf_token(None)[0]
    try:
        commit, files = hf_main_files(repo, token)
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError, KeyError, TypeError) as e:
        log(f"could not list the files of {repo} ({type(e).__name__}: {e}); its loader downloads them instead")
        return ""
    weights = weight_files(files)
    if not weights:
        return ""
    snap = hub_cache() / f"models--{repo.replace('/', '--')}" / "snapshots" / commit
    ver = base.Verified(folder / "openamika-verified.json")
    got = []
    for name, size, sha in weights:
        url = f"{base.HF}/{repo}/resolve/{commit}/{name}"
        got.append(base.fetch(url, snap / name, size, sha, ver, label=f"{repo}: {name}",
                              auth=token if token and base.token_goes_to(url) else None))
    total = sum(size for _, size, _ in weights)
    return (f"{', '.join(n for n, _, _ in weights)} ({total / 1e9:.1f} GB) "
            + ("downloaded and checked" if "downloaded" in got else "in place and checked"))


def ensure_hf_model(label: str, vpy: Path, folder: Path, repo: str, cmd: list[str], size: str,
                    args: argparse.Namespace) -> None:
    """A model the service downloads into the Hugging Face cache on its first start, fetched now instead: the
    service's own loader runs once with --download. A marker in the environment folder records that it finished."""
    marker = folder / "openamika-model.json"
    try:
        done = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        done = {}
    if Path(repo).expanduser().is_dir():           # settings.json names a model folder on this PC: nothing to fetch
        row("OK ", label, f"{repo} (a folder on this PC)")
        return
    snap = hf_cached(repo)
    if snap is not None and (done.get("model") == repo or args.check):
        row("OK ", label, f"{repo} in the Hugging Face cache ({snap.parent.parent})")
        return
    if args.check:
        raise SetupError(f"{repo} ({size}) is not downloaded yet: run this script without --check (otherwise the first "
                         "start downloads it)")
    log(f"downloading {repo} ({size}) into the Hugging Face cache (a public model; a Hugging Face token only makes it "
        "faster)")
    try:
        weights = prefetch_weights(repo, folder)
    except SetupError as e:
        raise SetupError(f"{repo} could not be downloaded: {e}. Run this script again: the download continues where it "
                         "stopped") from e
    # HF_HUB_VERBOSITY=error: the Hub's "you are sending unauthenticated requests" notice is not a problem here.
    # DISABLE_SAFETENSORS_CONVERSION: a model with only pytorch_model.bin (BAAI/bge-m3) would otherwise also fetch a
    # converted model.safetensors (2.3 GB more) from a pull request of the bot that converts them, in a thread the
    # download waits for; the services load the .bin either way.
    env = {**os.environ, "HF_HUB_VERBOSITY": os.environ.get("HF_HUB_VERBOSITY") or "error",
           "DISABLE_SAFETENSORS_CONVERSION": "1"}
    p = subprocess.run([str(vpy), "-X", "utf8", *cmd], cwd=str(ROOT), text=True, encoding="utf-8", errors="replace",
                       env=env)
    snap = hf_cached(repo)
    if p.returncode != 0 or snap is None:
        raise SetupError(f"{repo} could not be downloaded (see the lines above): check the internet connection and "
                         "run this script again (finished files are kept)")
    marker.write_text(json.dumps({"model": repo, "snapshot": str(snap), "at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}),
                      encoding="utf-8")
    row("OK ", label, f"{repo} in the Hugging Face cache ({snap.parent.parent}, downloaded"
                      + (f"; {weights}" if weights else "") + ")")


# ---- settings.json and brain/.env ---------------------------------------------------------------------------------
def settings_from_example(device: str, vision_on: bool) -> dict:
    """settings.example.json with this machine's environments and device: the interpreters found (a venv's or a conda
    environment's), the CPU instead of CUDA without an NVIDIA GPU, and her eyes on when they were installed."""
    cfg = json.loads((ROOT / "settings.example.json").read_text(encoding="utf-8-sig"))
    cfg["brain_python"] = rel(env_python(ENVS / "brain"))
    cfg["speech_python"] = rel(env_python(ENVS / "speech"))
    cfg.setdefault("embedder", {})["python"] = rel(env_python(ENVS / "embed"))
    cfg.setdefault("vision", {})["python"] = rel(env_python(ENVS / "vision"))
    if device == "cpu":
        cfg["speech_device"] = "cpu"
        cfg["embedder"].update(device="cpu", dtype="fp32")
        cfg["vision"]["device"] = "cpu"
    cfg["vision"]["enabled"] = bool(vision_on)
    return cfg


def read_settings() -> dict:
    """settings.json as a dict ({} when it is missing or cannot be read)."""
    try:
        cfg = json.loads((ROOT / "settings.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}
    return cfg if isinstance(cfg, dict) else {}


def settings_vision_enabled() -> bool:
    return bool((read_settings().get("vision") or {}).get("enabled"))


def chosen_models() -> tuple[str, str]:
    """(embedder model, vision model key) that an existing settings.json names, else settings.example.json's."""
    cfg = read_settings()
    emb = (cfg.get("embedder") or {}).get("model") if isinstance(cfg.get("embedder"), dict) else None
    vis = (cfg.get("vision") or {}).get("model") if isinstance(cfg.get("vision"), dict) else None
    return str(emb or EMBED_MODEL_DEFAULT), str(vis or VISION_MODEL_DEFAULT)


def vision_repo(key: str) -> str:
    """The Hugging Face repository of a vision model key, from vision/vlm_service.py's MODELS (read, not imported)."""
    import ast
    try:
        tree = ast.parse(VLM_SERVICE.read_text(encoding="utf-8"))
        table = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "MODELS" for t in n.targets))
        models = {str(k): str(v[0]) for k, v in table.items()}
    except (OSError, SyntaxError, ValueError, TypeError, AttributeError, IndexError, StopIteration):
        models = {VISION_MODEL_DEFAULT: "Qwen/Qwen3-VL-2B-Instruct"}
    if key not in models:
        raise SetupError(f"settings.json names the vision model {key!r}, which vision/vlm_service.py does not know "
                         f"(it knows {', '.join(sorted(models))}): fix \"vision\": {{\"model\": …}} in settings.json")
    return models[key]


def ensure_settings(device: str, vision_on: bool, args: argparse.Namespace) -> None:
    """settings.json: created from settings.example.json, or an existing one checked (never changed). It runs after
    the environment steps; an interpreter it names under envs\\ that is not there yet is left to that environment's
    own row (a failed or interrupted step), so a re-run never fails here for what it is still making."""
    path = ROOT / "settings.json"
    if not path.is_file():
        if args.check:
            raise SetupError("settings.json is not created yet: run this script without --check")
        cfg = settings_from_example(device, vision_on)
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        row("OK ", "settings.json", f"created from settings.example.json (interpreters in envs\\, speech on "
                                    f"{cfg['speech_device']}, vision {'on' if vision_on else 'off'})")
        return
    try:
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(cfg, dict):
            raise ValueError("not a JSON object")
    except (OSError, ValueError) as e:
        raise SetupError(f"settings.json cannot be read ({e}): fix it, or delete it and run this script again (it is "
                         "created again from settings.example.json)") from e
    eyes_on = bool((cfg.get("vision") or {}).get("enabled"))
    named = [("brain_python", cfg.get("brain_python")), ("speech_python", cfg.get("speech_python")),
             ("embedder.python", (cfg.get("embedder") or {}).get("python"))]
    if eyes_on:
        named.append(("vision.python", cfg["vision"].get("python")))
    missing, waiting = [], []
    for key, value in named:
        if not value or not isinstance(value, str):
            continue
        given = Path(value) if Path(value).is_absolute() else ROOT / value
        if given.is_file():
            continue
        folder, row_name = SETTINGS_ENVS[key]
        made = env_python(ENVS / folder)
        if key == "vision.python" and not vision_on and not made.is_file():
            raise SetupError("settings.json turns her eyes on (\"vision\": {\"enabled\": true}), but they are not "
                             "installed: run this script with --vision on, or set \"enabled\": false there")
        inside = given.resolve().is_relative_to(ENVS.resolve())
        if inside and not made.is_file():
            waiting.append(f"{value} (see the {row_name} row)")   # not made yet: that environment's row says why
        else:
            missing.append((key, value, made))
    if missing:
        key, value, made = missing[0]
        raise SetupError(f"settings.json names {value} as {key}, which does not exist" +
                         (f" (and {len(missing) - 1} more)" if len(missing) > 1 else "") +
                         f": point {key} at {rel(made)}" + (", the environment this script made" if made.is_file() else "") +
                         ", or delete settings.json and run this script again (it is created again)")
    if waiting:
        row("-- ", "settings.json", f"existing, not changed; it names {', '.join(waiting)}, which is not made yet")
        return
    note = ""
    if vision_on and not eyes_on:
        note = "; her eyes are installed but off: set \"vision\": {\"enabled\": true} to use them"
    row("OK ", "settings.json", f"existing, not changed (its interpreters exist{note})")


def ensure_env_file(args: argparse.Namespace) -> None:
    path = ROOT / "brain" / ".env"
    created = False
    if not path.is_file():
        if args.check:
            row("-- ", "brain/.env", "not created yet (this script copies .env.example there; the wizard writes your key)")
            return
        shutil.copyfile(ROOT / ".env.example", path)
        created = True
    key = ""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if line.strip().startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
    made = "created from .env.example; " if created else ""
    if key and not key.startswith("sk-or-v1-your"):
        row("OK ", "brain/.env", f"{made}OpenRouter key set (...{key[-4:]})")
    else:
        row("-- ", "brain/.env", f"{made}no OpenRouter key yet: the first-run wizard on the Use page takes it (or put it "
                                 "after OPENROUTER_API_KEY= in brain\\.env); fully local with Ollama needs none")


# ---- main -------------------------------------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Set up OpenAmika's brain, ears, memory and eyes (her voice and Live2D model: "
                                             "scripts/setup_tts.py)")
    ap.add_argument("--cpu", action="store_true", help="no NVIDIA GPU: CPU builds of torch; speech and memory run on the CPU")
    ap.add_argument("--vision", choices=("auto", "on", "off"), default="auto",
                    help="her eyes (the camera, Qwen3-VL-2B, ~4.3 GB of VRAM): auto installs them on a GPU with 16 GB or more")
    ap.add_argument("--python", default=None, help="the Python 3.11 to make the environments from (default: this one, "
                                                     "py -3.11, python3.11; then 3.12)")
    ap.add_argument("--check", action="store_true", help="report what is installed and what is missing; change nothing")
    ap.add_argument("--reinstall", action="store_true", help="run every pip step again")
    ap.add_argument("--no-token-prompt", action="store_true",
                    help="do not ask for a Hugging Face token (one in HF_TOKEN or a saved login is still used)")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:  # never die on a cp1252 console or a redirected log
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    ROWS.clear()
    t0 = time.time()
    log(f"OpenAmika setup -> {ROOT}{'  (--check: nothing is changed)' if args.check else ''}  "
        f"({platform.system()} {platform.machine()}, Python {platform.python_version()})")
    notes, cd = folder_notes(ROOT, caller_dir(), caller_shell())
    for note in notes:
        log(f"NOTE: {note}")
    if not args.check:
        free = base.disk_free_gb(ROOT)
        if free is not None and free < 40:
            log(f"WARNING: only {free:.0f} GB free; OpenAmika with her voice takes about 37 GB (about 28 GB without her "
                "eyes; `pip cache purge` afterwards gives back about 6 GB)")
        warning = long_folder_warning(ROOT)
        if warning:
            log(warning)
        if synced_by_onedrive(ROOT):
            log("WARNING: this folder is synced by OneDrive: its environments and models (tens of thousands of files, "
                "~37 GB) would be uploaded too. A folder outside OneDrive (for example C:\\OpenAmika) is better")
    rc = 0
    steps = base.Steps()
    try:
        mark, note = ask_hf_token(args)
        row(mark, "Hugging Face token", note)
        base_py: list[str] = []
        if not args.check:
            try:
                base_py, v = base.find_base_python(args.python)
                row("OK ", "Python", f"{'.'.join(map(str, v))} ({' '.join(base_py)})")
            except SetupError as e:
                row("!! ", "Python", str(e) if args.python else PYTHON_NEEDED)
                steps.failed.append("Python")
        gpu = None if args.cpu else gpu_info()
        device = "mac" if IS_MAC and not args.cpu else ("cuda" if gpu else "cpu")
        if gpu:
            row("OK ", "GPU", f"{gpu[0]}, {gpu[1] / 1024:.0f} GB: CUDA 12.8 builds")
        elif not IS_MAC:
            row("-- ", "GPU", "CPU builds (--cpu): speech recognition and memory run on the CPU, slower" if args.cpu else
                "no NVIDIA GPU found (nvidia-smi): CPU builds, so speech recognition and memory run on the CPU, slower. "
                "With an NVIDIA card, install its driver and run this script again")
        vision_on, why = vision_wanted(args.vision, device, gpu)
        if args.check:      # check what is there: her eyes count when installed, switched on, or asked for
            why = ("not installed yet: this script installs them on this GPU" if vision_on else
                   f"not installed ({why.removeprefix('skipped: ')})")
            vision_on = (ENVS / "vision").is_dir() or args.vision == "on" or settings_vision_enabled()
        needs = () if args.check else ("Python",)
        emb_model, vis_key = chosen_models()           # an existing settings.json may name other models
        steps.run("brain", ensure_env, "brain", base_py, device, args, needs=needs)
        steps.run("speech recognition", ensure_env, "speech", base_py, device, args, needs=needs)
        steps.run("speech model", ensure_speech_model, args)
        embed = steps.run("memory (embedder)", ensure_env, "memory", base_py, device, args, needs=needs)
        steps.run("memory model", ensure_hf_model, "memory model", embed, ENVS / "embed", emb_model,
                  ["brain/embed_server.py", "--download", "--model", emb_model],
                  "~2.3 GB" if emb_model == EMBED_MODEL_DEFAULT else "size depends on the model", args,
                  needs=("memory (embedder)",))
        if vision_on:
            eyes = steps.run("vision (her eyes)", ensure_env, "vision", base_py, device, args, needs=needs)
            steps.run("vision model", lambda: ensure_hf_model(
                "vision model", eyes, ENVS / "vision", vision_repo(vis_key),
                ["vision/vlm_service.py", "--download", "--model", vis_key],
                "~4.3 GB" if vis_key == VISION_MODEL_DEFAULT else "size depends on the model", args),
                needs=("vision (her eyes)",))
        else:
            row("-- ", "vision (her eyes)", why)
        # last: settings.json names the environments made above (a run stopped before them leaves none behind, and
        # a re-run after a failed step finds its own environments instead of a !! row for them)
        steps.run("settings.json", ensure_settings, device, vision_on, args)
        steps.run("brain/.env", ensure_env_file, args)
    except KeyboardInterrupt:
        row("!! ", "interrupted", "Ctrl-C (run this script again to resume; finished steps are kept)")
        rc = 130

    width = max((len(n) for _, n, _ in ROWS), default=10)
    print("\n" + "=" * 78)
    print(f"OpenAmika setup summary ({time.time() - t0:.0f} s)")
    for mark, name, detail in ROWS:
        print(f"  {mark}{name.ljust(width)}  {detail}")
    bad = rc != 0 or any(m.strip() == "!!" for m, _, _ in ROWS)
    print("=" * 78)
    brain_py = rel(env_python(ENVS / "brain"))
    for note in notes:
        print(note)
    if bad:
        print("Fix the !! lines above and run this script again (finished steps are skipped)." if not args.check else
              "Not ready: run this script without --check to install what is missing.")
        if cd:
            print(f"  (from her folder: {cd})")
    elif args.check:
        print("Her brain, ears, memory" + (" and eyes" if vision_on else "") + " are installed.")
    else:
        voice = f"{brain_py} {os.path.join('scripts', 'setup_tts.py')}"
        # PowerShell runs nothing from the current folder without .\ (cmd accepts it as well)
        start = ".\\Start_OpenAmika.bat" if IS_WIN else f"{brain_py} launch.py"
        pad = max(len(voice), len(start), len(cd)) + 3
        print("Done. Next:")
        if cd:
            print(f"  0. {cd.ljust(pad)}go into her folder first: the two lines below run there")
        print(f"  1. {voice.ljust(pad)}her voice, her Live2D model and the paper doll (type yes to accept her license)")
        print(f"  2. {start.ljust(pad)}start her; the page opens at http://localhost:53000")
    return rc or (1 if bad else 0)


if __name__ == "__main__":
    raise SystemExit(main())
