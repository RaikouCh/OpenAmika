#!/usr/bin/env python3
# Copyright (c) 2026 MekaHime Inc.
# SPDX-License-Identifier: MIT
"""Install Amika's voice, her Live2D model and the paper doll that stands in for her helpers (from Hugging Face) and
the OpenAmika voice server (a MekaHime build of GPT-SoVITS) that speaks with that voice.

    envs\\brain\\Scripts\\python.exe scripts\\setup_tts.py   # Windows, after scripts\\setup_windows.ps1 (any Python 3.11 works)
    python scripts/setup_tts.py --cpu                # no NVIDIA GPU: CPU torch (slow)
    python scripts/setup_tts.py --accept-voice-license   # unattended: accept her license up front
    python scripts/setup_tts.py --verify             # check everything file by file; download and install nothing
    python scripts/setup_tts.py --assets-only        # only her voice, her Live2D model and the paper doll, no voice server
    python scripts/setup_tts.py --from-dir <folder>  # her files from a local copy of the repository (offline)
    python scripts/setup_tts.py --self-test          # also start the server once and synthesize a line

First it shows her personal-use license in short and asks you to type yes (her voice, her Live2D model and the paper
doll share one license), so the rest can run unattended. Then:

1. Her voice, her Live2D model and the paper doll, from the Hugging Face repository MekaHime/MekaHime_Amika at pinned
   revisions, file by file with the standard library (no venv needed, so a failed torch install never costs her voice
   or her body). Every file is checked against its size and SHA-256 in scripts/MekaHime_Amika.manifest.json:
     vendor/tts-engine/Speakers/MekaHime_Amika/   her voice: character.json, MekaHime_Amika.ckpt (GPT weights),
                                                  MekaHime_Amika.pth (SoVITS weights), references/emotions.json and one
                                                  clip per emotion tag (69), the README and LICENSE of the repository
     avatar/models/Amika/                         her Live2D model (live2d/Amika in the repository), where the Use page
                                                  finds it; a banks.json edited on the Setup page is never overwritten
     avatar/models/Host/                          the paper doll (live2d/Host in the repository): MekaHime's folded-paper
                                                  shrine doll, which the Use page seats beside her while a task agent
                                                  (Hermes Agent, nanoMuse) is switched on; its banks.json says
                                                  "role": "agent". Pinned at its own revision (PAPER_DOLL_REV)
   The repository is public from OpenAmika's public release on; before that it needs a Hugging Face read token in
   HF_TOKEN (or a saved `hf auth login`). The token goes to huggingface.co only (never to the CDN it redirects to,
   nor to a mirror) and is never printed or saved. HF_ENDPOINT picks a mirror, as in huggingface_hub; every file is
   still checked against its pinned SHA-256.
2. The voice server in vendor/tts-engine/ (everything but main.py and the docs is git-ignored):
     .venv/          Python 3.11 venv (3.12 works, untested): torch + torchaudio 2.9.1 (cu128 / cpu) +
                     requirements-tts.txt
     GPT-SoVITS/     upstream RVC-Boss/GPT-SoVITS at a pinned commit (MIT), with its pretrained models (HuBERT,
                     RoBERTa, ERes2NetV2 speaker model, G2PW, fastText language ID) and the Japanese user dictionary
                     its front-end builds on first use
     nltk_data/      English POS tagger + CMUdict for the English front-end
     ffmpeg/         ffmpeg + ffprobe for Opus output (optional: WAV works without it)
3. Checks: the voice has a clip for every tag OpenAmika's voice adapter (speech/voice_adapter.py) can send, each Live2D
   model has every file its .model3.json names (the paper doll also its "role": "agent"), and settings.json starts
   this server (services.tts) with that voice (tts_character). settings.json is never edited.

Needs Python 3.11 or 3.12 (scipy, onnxruntime and matplotlib at the pinned versions have no wheels for 3.10, and
upstream's numpy<2 has none for 3.13); Linux with glibc 2.28 or newer; macOS 14 or newer on Apple Silicon.

Integrity: every model and data file, every file of her voice and Live2D model (at a pinned revision of her
repository) and the Windows ffmpeg build are checked against a size and SHA-256 pinned here or in the manifest; a
download that does not match fails at once instead of being retried. GPT-SoVITS is pinned by commit: git checks the
objects it fetches. Without git, the zip GitHub serves for that commit is checked before unpacking against a pinned
SHA-256 over all 282 of its files (see tree_digest), and the unpacked GPT_SoVITS/TTS_infer_pack/TTS.py against its
own pinned SHA-256, again on every re-run (for a git checkout too). The Linux ffmpeg build comes from a rolling
release and is checked against the SHA-256 GitHub lists for that file, and Python packages come from PyPI / the
PyTorch index at pinned versions. Downloads resume from .part files. Re-running skips what is already present and
verified (hashes are cached by size and modification time), so it is also the repair: a failed step is reported, the
steps that do not depend on it still run, the summary at the end lists every step (OK, -- skipped or optional, !!
failed, each with its fix) and the exit code is 1 if any failed (130 after Ctrl-C).
Only the standard library is used here; packages are installed into the venv this script creates.
"""
from __future__ import annotations

import argparse
import errno
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ENGINE = ROOT / "vendor" / "tts-engine"
ENGINE_FILES = ("main.py", "requirements-tts.txt", "README.md", "LICENSE", "THIRD_PARTY_NOTICES.md")
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
UA = {"User-Agent": "OpenAmika-voice-setup/1.0"}

# ---- pins -------------------------------------------------------------------------------------
GPT_SOVITS_GIT = "https://github.com/RVC-Boss/GPT-SoVITS.git"
GPT_SOVITS_ZIP = "https://codeload.github.com/RVC-Boss/GPT-SoVITS/zip/{commit}"
GPT_SOVITS_COMMIT = "b4570b876f5c086819ba84e3215472733c6a7b70"   # main @ 2026-10-19, v2ProPlus + TTS_infer_pack
# Checks for the zip fallback (no git). Both values were computed from GitHub's zip of the commit and from a git
# checkout of it (core.autocrlf=false), which agree:
#   the SHA-256 of the lines "<sha256 of file>  <path>\n" (sorted by path) over the 282 files (see tree_digest), and
#   the SHA-256 of GPT_SoVITS/TTS_infer_pack/TTS.py, the module main.py imports (raw.githubusercontent.com agrees).
GPT_SOVITS_TREE_SHA256 = "6f924a174f64f4437aa4e3e754657bce6c8e7634ea492e68459536c77ae2ec34"
GPT_SOVITS_TTS_PY = ("GPT_SoVITS/TTS_infer_pack/TTS.py", "6a80acef239829a5af42916bb1f38598d9fd3ffc49d939601d3153a1f1484fd0")
# tracked files upstream rewrites by itself while it runs (caches and its default config); not local edits
GPT_SOVITS_SELF_WRITTEN = {"GPT_SoVITS/text/g2pw/polyphonic.md5", "GPT_SoVITS/text/g2pw/polyphonic.pickle",
                           "GPT_SoVITS/configs/tts_infer.yaml"}

TORCH_VERSION = "2.9.1"           # same torch/torchaudio pair the previous engine ran on an RTX 5070 (CUDA 12.8)
TORCH_INDEX = {"cuda": "https://download.pytorch.org/whl/cu128", "cpu": "https://download.pytorch.org/whl/cpu"}
TORCH_LOCAL = {"cuda": "+cu128", "cpu": "+cpu"}
# scipy 1.17.1, onnxruntime 1.31.0 and matplotlib 3.11.2 need 3.11+; numpy<2 (upstream pin) has no wheels for 3.13
PY_MIN, PY_MAX, PY_TESTED = (3, 11), (3, 12), (3, 11)
GLIBC_MIN = (2, 28)               # torch 2.9.1, onnxruntime 1.31.0, soundfile 0.14.0: manylinux_2_28 wheels only
MACOS_MIN = (14, 0)               # onnxruntime 1.31.0: one macOS wheel, macosx_14_0_arm64, and no source package

HF_SITE = "https://huggingface.co"                         # the pages people open (license, model card)
HF = (os.environ.get("HF_ENDPOINT") or HF_SITE).rstrip("/")  # where files come from; HF_ENDPOINT picks a mirror, as
                                                             # in huggingface_hub (every file is pinned by SHA-256)
TOKEN_HOSTS = ("huggingface.co",)   # a Hugging Face token goes to these hosts (and their subdomains) only: never to a
                                    # mirror that HF_ENDPOINT names (a mirror serves public files and needs none)
PRETRAINED_REPO, PRETRAINED_REV = "lj1995/GPT-SoVITS", "8f8857563c040d542de108a2c18b0425abd6c9c5"
PRETRAINED = [  # path in lj1995/GPT-SoVITS == path under GPT_SoVITS/pretrained_models, size, sha256
    ("chinese-hubert-base/config.json", 1449, "c3e5060a1277e0f078cc6be9da4528a605dba6ece93018981fe2c820e5c7b103"),
    ("chinese-hubert-base/preprocessor_config.json", 212, "dcd684124d06722947939d41ea6ae58dbf10968c60a11a29f23ddc602c64a29b"),
    ("chinese-hubert-base/pytorch_model.bin", 188811417, "24164f129c66499d1346e2aa55f183250c223161ec2770c0da3d3b08cf432d3c"),
    ("chinese-roberta-wwm-ext-large/config.json", 963, "3d57de2fd7e80d0e5c8ff194f0bbb6baa10df7e43fc262a0cc71298a78b0a3e5"),
    ("chinese-roberta-wwm-ext-large/tokenizer.json", 268962, "173796956820ea27bd14f76bf28162607ff4254807e2948253eb5b46f5bb643b"),
    ("chinese-roberta-wwm-ext-large/pytorch_model.bin", 651225145, "e53a693acc59ace251d143d068096ae0d7b79e4b1b503fa84c9dcf576448c1d8"),
    ("sv/pretrained_eres2netv2w24s4ep4.ckpt", 107528697, "4f5a0bf73c61eb41b174e1bb54e7ee3c83233892be8e0af1f187024e8e581a35"),
]
G2PW_REPO, G2PW_REV = "XXXXRT/GPT-SoVITS-Pretrained", "0c47645e02a7bc3688d7b263b0042c81e3cd82cd"
G2PW_ZIP = ("G2PWModel.zip", 588856634, "46292be0374a49308069233cd5c147ae4c41806558e4781a2467a31a4d8099da")
G2PW_ONNX = ("g2pW.onnx", 635212732, "2eb3c71fd95117b2e1abef8d2d0cd78aae894bbe7f0fac105ddc9c32ce63cbd0")
LANGID = ("https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.bin", 131266198,
          "7e69ec5451bc261cc7844e49e4792a85d7f09c06789ec800fc4a44aec362764e")
NLTK_COMMIT = "550b6625bcef1f2abff2ff770a5a0d272c9c6b2a"
NLTK = [  # g2p_en checks the first and last zip at import; nltk>=3.9 pos_tag reads the *_eng tagger
    ("taggers/averaged_perceptron_tagger.zip", 2526731, "e1f13cf2532daadfd6f3bc481a49859f0b8ea6432ccdcd83e6a49a5f19008de9"),
    ("taggers/averaged_perceptron_tagger_eng.zip", 1539115, "6025f530624335c67d6547d44757b357b4e79bae030a0383e9887a92c1718f0b"),
    ("corpora/cmudict.zip", 896069, "d07cca47fd72ad32ea9d8ad1219f85301eeaf4568f8b6b73747506a71fb5afd6"),
]
FFMPEG_WIN = ("https://github.com/GyanD/codexffmpeg/releases/download/8.0.1/ffmpeg-8.0.1-essentials_build.zip",
              106259850, "e2aaeaa0fdbc397d4794828086424d4aaa2102cef1fb6874f6ffd29c0b88b673")
# BtbN's static Linux builds are re-published daily under the release tag "latest"; its asset list (GitHub API) gives
# each file's size and SHA-256. The newest release branch is taken (ffmpeg-nX.Y-latest-linux64-gpl-X.Y.tar.xz).
FFMPEG_LINUX_RELEASE = "https://api.github.com/repos/BtbN/FFmpeg-Builds/releases/tags/latest"
FFMPEG_LINUX_ASSET = re.compile(r"ffmpeg-n(\d+)\.(\d+)-latest-linux64-gpl-\1\.\2\.tar\.xz")

VOICE_REPO, VOICE_ID = "MekaHime/MekaHime_Amika", "MekaHime_Amika"
VOICE_REV = "a3934e5a83dcb0192901f69536c66b837414e822"    # 2026-11-03: v1.0, 69 emotion tags, each with its clip
# Every file of that revision with its size and SHA-256 (250 files): her voice is everything outside live2d/, her
# Live2D model is live2d/Amika/. Update it together with VOICE_REV (--write-manifest <local copy of the repository>).
# The paper doll (live2d/Host/, below) has a block of its own there, "paper_doll", pinned at PAPER_DOLL_REV.
MANIFEST = Path(__file__).resolve().with_name("MekaHime_Amika.manifest.json")
REPO_ONLY = (".gitattributes",)                           # repository plumbing, not part of her voice
# OpenAmika's voice adapter: its V1_IDS are every tag it can send to the voice server (checked in check_voice)
VOICE_ADAPTER = ROOT / "speech" / "voice_adapter.py"
# Amika's Live2D model is in the same repository (same license) under live2d/Amika; it goes to avatar/models/Amika
AVATAR_ID, AVATAR_PATH = "Amika", "live2d/Amika"
# The paper doll that stands in for her helpers (task agents: Hermes Agent, nanoMuse) on the Use page: MekaHime's
# folded-paper shrine doll, in the same repository (same license) under live2d/Host. It goes to avatar/models/Host; its
# banks.json says "role": "agent", which keeps it out of her model picker. Its 70 files are pinned by size and SHA-256
# in the manifest's "paper_doll" block, at a revision of their own:
PAPER_DOLL_ID, PAPER_DOLL_PATH = "Host", "live2d/Host"
# 2026-11-05: the revision that adds live2d/Host/ (and names the doll in the model card and LICENSE). The full
# 40-character commit; the pins above need no change (see "A new revision of her Hugging Face repository" in
# README_IF_YOU_ARE_AI_AGENT.md). Empty would mean: the doll is never downloaded and its row says so; --from-dir still
# installs it from a local copy, checked file by file against the pins.
PAPER_DOLL_REV = "b3ffaf59f4d5f192155cffd79539e9911b610f5a"

ROWS: list[tuple[str, str, str]] = []   # (mark, name, detail) for the final summary


def log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def row(mark: str, name: str, detail: str) -> None:
    ROWS.append((mark, name, detail))


class SetupError(RuntimeError):
    pass


class IntegrityError(SetupError):
    """A complete download does not match its pinned hash: downloading it again will not help."""


class HTTPStatusError(SetupError):
    """A download the server refused with an HTTP status that asking again will not change (401, 403, 404, ...).
    error_code is Hugging Face's X-Error-Code header (RepoNotFound, GatedRepo, EntryNotFound, ...) when present."""

    def __init__(self, url: str, code: int, reason: str, error_code: str = "") -> None:
        super().__init__(f"{url}: HTTP {code} {reason}")
        self.url, self.code, self.error_code = url, code, error_code


class SameHostAuthRedirect(urllib.request.HTTPRedirectHandler):
    """urllib's redirects, except that an Authorization header goes along to the same host only. Hugging Face answers
    a file of a private repository with a redirect to its CDN (another host), which must never see the token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        auth = req.get_header("Authorization")
        if new is not None and auth and \
                urllib.parse.urlsplit(newurl).netloc == urllib.parse.urlsplit(req.full_url).netloc:
            new.add_unredirected_header("Authorization", auth)
        return new


OPENER = urllib.request.build_opener(SameHostAuthRedirect)


# ---- small helpers ------------------------------------------------------------------------------
def run(cmd: list[str], *, cwd: Optional[Path] = None, env: Optional[dict] = None, check: bool = True,
        capture: bool = False) -> subprocess.CompletedProcess:
    shown = " ".join(c if " " not in c else f'"{c}"' for c in cmd)
    if not capture:
        log(f"$ {shown}")
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, text=True, encoding="utf-8", errors="replace",
                       capture_output=capture)
    if check and p.returncode != 0:
        tail = (p.stdout or "")[-1500:] + (p.stderr or "")[-1500:] if capture else ""
        raise SetupError(f"command failed ({p.returncode}): {shown}\n{tail}".rstrip())
    return p


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8 << 20), b""):
            h.update(block)
    return h.hexdigest()


def token_goes_to(url: str) -> bool:
    """True when a Hugging Face token may be sent to url's host: huggingface.co itself (TOKEN_HOSTS), not a mirror."""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in TOKEN_HOSTS)


SHORT_FOLDER = 100   # Windows: from a longer folder, DLLs deep in the environments fail to load (long paths on or off)
TOO_LONG = ("filename or extension is too long", "[winerror 206]", "ファイル名または拡張子が長すぎます", "文件名或扩展名太长")


def too_long_hint(text: str) -> str:
    """The fix for Windows' "The filename or extension is too long" (error 206, also inside a DLL load failure), or ''.
    Running the setup again in the same folder cannot fix it: only a shorter folder does."""
    low = (text or "").lower()
    if not any(mark in low for mark in TOO_LONG):
        return ""
    return ("the folder path is too long for Windows (\"The filename or extension is too long\"): move OpenAmika to a "
            "short folder such as C:\\OpenAmika and run the setup there; running it again here does not help")


def long_folder_warning(folder: Path) -> str:
    """A warning when a Windows folder is too long for what the setup puts under it, or ''."""
    n = len(str(folder))
    if not IS_WIN:
        return ""
    if n > SHORT_FOLDER:
        return (f"WARNING: {folder} is {n} characters long. Windows cannot load some program files (DLLs) deep in the "
                "environments from a folder that long, even with long paths enabled (\"The filename or extension is "
                "too long\"). Move OpenAmika to a short folder such as C:\\OpenAmika and run the setup there")
    if n > 60 and not long_paths_enabled():
        return (f"WARNING: {folder} is {n} characters long and Windows long paths are off; files deep in the "
                "environments can pass the 260-character limit. A short folder such as C:\\OpenAmika is safer")
    return ""


class Verified:
    """Remembers files already hashed (by size + mtime) so a re-run does not re-hash gigabytes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def ok(self, f: Path, size: int, sha: str) -> bool:
        if not f.is_file() or f.stat().st_size != size:
            return False
        return self.sha256(f) == sha

    def sha256(self, f: Path) -> str:
        """The file's SHA-256, hashed again only when its size or modification time changed."""
        st = f.stat()
        rec = self.data.get(str(f))
        if rec and rec.get("mtime_ns") == st.st_mtime_ns and rec.get("size") == st.st_size and rec.get("sha256"):
            return str(rec["sha256"])
        got = sha256_file(f)
        self.record(f, st.st_size, got)
        return got

    def record(self, f: Path, size: int, sha: str) -> None:
        self.data[str(f)] = {"sha256": sha, "size": size, "mtime_ns": f.stat().st_mtime_ns}
        self.save()

    def installed(self, f: Path) -> None:
        """Remember the SHA-256 of a file this script just put in place (her banks.json), so a later pin can replace
        it while it is unchanged and an edit made after the install is kept."""
        self.data.setdefault("_installed", {})[str(f)] = self.sha256(f)
        self.save()

    def as_installed(self, f: Path) -> bool:
        """f is still exactly the file this script installed (not edited since)."""
        want = (self.data.get("_installed") or {}).get(str(f))
        return bool(want) and f.is_file() and self.sha256(f) == want

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1), encoding="utf-8")


RETRY_HTTP = (408, 425, 429, 500, 502, 503, 504)   # worth asking again; any other HTTP error fails at once


def progress_line(name: str, done: int, total: int, rate: float) -> str:
    """One progress line of a download: 'model.pt: 412 / 937 MB (43%), 8.1 MB/s, 525 MB left, about 1 min' (without a
    known total: what arrived so far and the speed)."""
    speed = f"{rate / 1e6:.1f} MB/s" if rate >= 1e5 else f"{rate / 1e3:.0f} KB/s"
    if not total:
        return f"{name}: {done / 1e6:,.0f} MB so far, {speed}"
    left = max(0, total - done)
    left_text = f"{left / 1e9:.1f} GB" if left >= 1e9 else f"{left / 1e6:,.0f} MB"
    when = ""
    if rate > 0 and left:
        eta = left / rate
        when = f", about {eta / 3600:.1f} h" if eta >= 5400 else f", about {max(1, round(eta / 60))} min"
    return f"{name}: {done / 1e6:,.0f} / {total / 1e6:,.0f} MB ({done * 100 // total}%), {speed}, {left_text} left{when}"


def remote_size(r: Any, have: int) -> Optional[int]:
    """Full size of the file behind a response: the total of a 206's Content-Range, else Content-Length."""
    total = (r.headers.get("Content-Range") or "").rpartition("/")[2].strip()
    if r.status == 206 and total.isdigit():
        return int(total)
    length = (r.headers.get("Content-Length") or "").strip()
    return int(length) + (have if r.status == 206 else 0) if length.isdigit() else None


def fetch(url: str, dest: Path, size: Optional[int], sha: Optional[str], ver: Optional[Verified] = None,
          headers: Optional[dict] = None, retries: int = 4, label: Optional[str] = None, resume: bool = True,
          auth: Optional[str] = None) -> str:
    """Download url -> dest through a resumable .part file, then check size and SHA-256. Returns 'present' (already
    there and verified) or 'downloaded'.

    Network errors, timeouts, short reads and HTTP 408/425/429/5xx are retried, up to `retries` tries in all, each
    resuming the .part file. A mismatch is not retried: a file that does not have its pinned size (the server
    announces another size, or more bytes arrive) or whose complete download has the wrong SHA-256 is deleted and
    raises IntegrityError at once, since the same address would serve the same wrong file again. The one exception
    is a download that continued a .part left by an earlier run, which may have been stale: it gets one fresh start.
    resume=False (for a file whose bytes may change between requests: a release listing, an archive GitHub builds
    on request) never continues a .part, not even within one call. auth (a Hugging Face token) is sent as a bearer
    Authorization header to url's own host only (see SameHostAuthRedirect). Any other HTTP error raises
    HTTPStatusError at once."""
    if sha and size and ver is not None and ver.ok(dest, size, sha):
        return "present"
    if label or (size and size > 50e6):
        log(f"downloading {label or dest.name}" + (f" ({size / 1e6:,.0f} MB)" if size else ""))
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    fresh_start_left = True
    attempt = 0
    while True:
        attempt += 1
        try:
            if not resume:                       # every try starts from the first byte
                part.unlink(missing_ok=True)
            have = part.stat().st_size if part.exists() else 0
            if size and have > size:
                part.unlink()
                have = 0
            resumed = have > 0
            if not (size and have == size):      # a complete .part from an interrupted run needs no request
                req = urllib.request.Request(url, headers={**UA, **(headers or {})})
                if auth:
                    req.add_unredirected_header("Authorization", "Bearer " + auth)
                if have:
                    req.add_header("Range", f"bytes={have}-")
                with OPENER.open(req, timeout=60) as r:
                    if have and r.status != 206:     # server ignored the range: start over
                        have, resumed = 0, False
                    announced = remote_size(r, have)
                    if size and announced is not None and announced != size:
                        part.unlink(missing_ok=True)
                        raise IntegrityError(f"{dest.name}: {url} serves {announced:,} bytes, the pinned file has "
                                             f"{size:,}. The file at that address is not the pinned one.")
                    total = size or announced or 0
                    t_last = time.time()
                    done = done_last = have
                    if have:
                        log(f"  {dest.name}: continuing at {have / 1e6:,.0f} MB (an earlier run stopped there)")
                    hinted = False
                    with open(part, "ab" if have else "wb") as f:
                        while True:
                            block = r.read(1 << 20)
                            if not block:
                                break
                            f.write(block)
                            done += len(block)
                            if time.time() - t_last > 10:
                                rate = (done - done_last) / max(1e-6, time.time() - t_last)
                                line = progress_line(dest.name, done, total, rate)
                                if not hinted and not auth and rate < 300e3 and token_goes_to(url):
                                    hinted = True     # Hugging Face throttles anonymous downloads
                                    line += ("; slow: Hugging Face throttles downloads without a token (free at "
                                             "https://huggingface.co/settings/tokens; set HF_TOKEN and run this again, "
                                             "it continues here)")
                                log("  " + line)
                                t_last, done_last = time.time(), done
            got_size = part.stat().st_size
            if size and got_size < size:         # the connection ended early: retried, resuming
                raise SetupError(f"{dest.name}: got {got_size:,} of {size:,} bytes")
            if size and got_size > size:
                part.unlink()
                raise IntegrityError(f"{dest.name}: got {got_size:,} bytes from {url}, the pinned file has {size:,}")
            if sha:
                got = sha256_file(part)
                if got != sha:
                    part.unlink()
                    if resumed and fresh_start_left:
                        fresh_start_left = False
                        attempt -= 1             # a fresh start is not a failed try
                        log(f"  {dest.name}: SHA-256 mismatch after continuing an earlier partial download; "
                            "downloading it once more from the start")
                        continue
                    raise IntegrityError(f"{dest.name}: SHA-256 mismatch (got {got[:16]}…, expected {sha[:16]}…) "
                                         f"for {url}. The file at that address is not the pinned one.")
            os.replace(part, dest)
            if sha and size and ver is not None:
                ver.record(dest, size, sha)      # just hashed above
            return "downloaded"
        except IntegrityError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 416:                    # a stale .part the server cannot continue: start over
                part.unlink(missing_ok=True)
            elif e.code not in RETRY_HTTP:
                raise HTTPStatusError(url, e.code, str(e.reason), (e.headers or {}).get("X-Error-Code") or "") from e
            err: Exception = e
        except (urllib.error.URLError, http.client.HTTPException, OSError, SetupError) as e:
            if isinstance(e, OSError) and e.errno == errno.ENOSPC:
                raise SetupError(f"{dest.parent}: the disk is full") from e
            err = e
        if attempt >= retries:
            raise SetupError(f"download failed after {retries} tries: {url}: {err}") from err
        log(f"  {dest.name}: {err} (retrying in {3 * attempt} s)")
        time.sleep(3 * attempt)


def safe_members(names: list[str], dest: Path) -> None:
    root = dest.resolve()
    for n in names:
        target = (dest / n).resolve()
        if root != target and root not in target.parents:
            raise SetupError(f"archive member escapes the target folder: {n}")


def disk_free_gb(path: Path) -> Optional[float]:
    p = path
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return shutil.disk_usage(p).free / 1e9
    except OSError:
        return None


# ---- python + venv ------------------------------------------------------------------------------
def py_version(cmd: list[str]) -> Optional[tuple[int, int, int]]:
    try:
        p = subprocess.run(cmd + ["-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
                           capture_output=True, text=True, timeout=30)
        if p.returncode == 0:
            return tuple(int(x) for x in p.stdout.strip().split("."))  # type: ignore[return-value]
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def ok_version(v: Optional[tuple]) -> bool:
    return v is not None and PY_MIN <= v[:2] <= PY_MAX


PY_RANGE = f"{PY_MIN[0]}.{PY_MIN[1]} or {PY_MAX[0]}.{PY_MAX[1]}"


def find_base_python(explicit: Optional[str]) -> tuple[list[str], tuple[int, int, int]]:
    """The interpreter the venv is made from: --python if given, else the first Python 3.11 found (this one, then
    `py -3.11` / python3.11), else the first 3.12 (it should work but has not been tested)."""
    if explicit:
        v = py_version([explicit])
        if not ok_version(v):
            raise SetupError(f"--python {explicit} is {'Python ' + '.'.join(map(str, v)) if v else 'not a working Python'}; "
                             f"the voice engine needs Python {PY_RANGE}")
        return [explicit], v  # type: ignore[return-value]
    cands: list[list[str]] = [[sys.executable]]
    if IS_WIN:
        cands += [["py", "-3.11"], ["py", "-3.12"]]
    cands += [[n] for n in ("python3.11", "python3.12") if shutil.which(n)]
    usable: list[tuple[list[str], tuple[int, int, int]]] = []
    for c in cands:
        v = py_version(c)
        if ok_version(v):
            if v[:2] == PY_TESTED:  # type: ignore[index]
                return c, v  # type: ignore[return-value]
            usable.append((c, v))  # type: ignore[arg-type]
    if usable:
        c, v = usable[0]
        log(f"no Python 3.11 found; using {' '.join(c)} (Python {v[0]}.{v[1]}: it should work, but only 3.11 is tested)")
        return c, v
    raise SetupError(f"the voice engine needs Python {PY_RANGE} (3.11 recommended): scipy, onnxruntime and matplotlib at "
                     "the pinned versions need 3.11+, and upstream pins numpy<2, which has no wheels for 3.13+. Install "
                     "Python 3.11 (python.org; Debian/Ubuntu: python3.11 and python3.11-venv) and re-run, or pass "
                     "--python <path>.")


def venv_python(engine: Path) -> Path:
    return engine / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")


def pip_works(vpy: Path) -> bool:
    try:
        return subprocess.run([str(vpy), "-m", "pip", "--version"], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_venv(engine: Path, explicit_python: Optional[str]) -> Path:
    venv = engine / ".venv"
    vpy = venv_python(engine)
    clear = False
    if vpy.exists():
        v = py_version([str(vpy)])
        if v is not None and not ok_version(v):
            raise SetupError(f"{venv} uses Python {'.'.join(map(str, v))}; the voice engine needs {PY_RANGE}. "
                             "Delete that folder and re-run")
        if v is not None and pip_works(vpy):
            row("OK ", "venv", f"{vpy} (Python {'.'.join(map(str, v))}, existing)")
            return vpy
        # a venv an earlier run did not finish (Debian/Ubuntu without pythonX.Y-venv leaves one without pip)
        log(f"{venv} is incomplete ({'its Python does not start' if v is None else 'it has no pip'}); creating it again")
        clear = True
    elif venv.is_dir() and any(venv.iterdir()):
        clear = True
    base, v = find_base_python(explicit_python)
    log(f"creating {venv} with Python {'.'.join(map(str, v))} ({' '.join(base)})")
    try:
        run(base + ["-m", "venv", *(["--clear"] if clear else []), str(venv)])
    except SetupError as e:
        hint = f" (Debian/Ubuntu: sudo apt install python{v[0]}.{v[1]}-venv)" if IS_LINUX else ""
        raise SetupError(f"{e}{hint}") from e
    if not pip_works(vpy):
        raise SetupError(f"{venv} was created without pip" +
                         (f" (Debian/Ubuntu: sudo apt install python{v[0]}.{v[1]}-venv)" if IS_LINUX else ""))
    run([str(vpy), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-U", "pip", "wheel"])
    row("OK ", "venv", f"{vpy} (Python {'.'.join(map(str, v))}, {'created again' if clear else 'created'})")
    return vpy


def pip(vpy: Path, *args: str) -> None:
    extra = [] if sys.stdout.isatty() else ["--progress-bar", "off"]
    run([str(vpy), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--timeout", "60",
         "--retries", "5", *extra, *args])


def has_nvidia_gpu() -> bool:
    exe = shutil.which("nvidia-smi")
    if not exe and IS_WIN:
        cand = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        exe = str(cand) if cand.exists() else None
    if not exe:
        return False
    try:
        p = subprocess.run([exe, "-L"], capture_output=True, text=True, timeout=30)
        return p.returncode == 0 and "GPU" in p.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


def pick_device(args: argparse.Namespace) -> str:
    if args.cpu or args.device == "cpu":
        return "cpu"
    if IS_MAC:
        return "mac"            # PyPI torch: CPU + Apple MPS
    if args.device == "cuda":
        return "cuda"
    return "cuda" if has_nvidia_gpu() else "cpu"


def sysctl(name: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def version_tuple(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", text)[:2])


def check_platform(vpy: Path) -> None:
    """Fail early, with the reason, where the pinned packages have no wheels (pip would fail on a source build)."""
    text_only = "OpenAmika itself still runs without her voice server; she then answers in text only."
    if IS_LINUX:
        lib, ver = platform.libc_ver()
        if lib == "glibc" and ver and version_tuple(ver) < GLIBC_MIN:
            raise SetupError(f"glibc {ver} is too old: torch 2.9.1, onnxruntime 1.31.0 and soundfile 0.14.0 have Linux "
                             f"wheels for glibc {GLIBC_MIN[0]}.{GLIBC_MIN[1]}+ only (Ubuntu 20.04+, Debian 10+, RHEL / "
                             f"Rocky 8+). {text_only}")
    if IS_MAC:
        p = subprocess.run([str(vpy), "-c", "import platform; print(platform.machine())"], capture_output=True, text=True)
        arch = p.stdout.strip() or platform.machine()
        if arch != "arm64":
            if sysctl("hw.optional.arm64") == "1":   # an x86_64 Python under Rosetta on an Apple Silicon Mac
                raise SetupError(f"{vpy} runs as {arch} under Rosetta, and PyTorch / onnxruntime need a native arm64 "
                                 "Python on Apple Silicon. Install Python 3.11 for arm64 (python.org's macOS installer, "
                                 f"or Homebrew in /opt/homebrew), delete {vpy.parent.parent} and re-run this script with "
                                 "that Python from a terminal that is not running under Rosetta.")
            raise SetupError("PyTorch 2.9 has no wheels for Intel Macs; the voice engine needs Windows/Linux "
                             f"(NVIDIA GPU) or an Apple Silicon Mac. {text_only}")
        mac = sysctl("kern.osproductversion") or platform.mac_ver()[0]
        if mac and version_tuple(mac) < MACOS_MIN:
            raise SetupError(f"macOS {mac}: the voice engine needs macOS {MACOS_MIN[0]} or newer (onnxruntime 1.31.0, "
                             f"used by the Chinese front-end, ships a macOS {MACOS_MIN[0]}+ wheel only). {text_only}")


def ensure_torch(vpy: Path, device: str, reinstall: bool) -> Path:
    check_platform(vpy)
    local = "" if device == "mac" else TORCH_LOCAL[device]
    want = f"{TORCH_VERSION}{local}"
    probe = ("import importlib.metadata as md, json\n"
             "out = {}\n"
             "try:\n"
             "    out['installed'] = md.version('torch')\n"
             "except Exception:\n"
             "    pass\n"
             "try:\n"
             "    import torch, torchaudio\n"
             "    out.update(torch=torch.__version__, torchaudio=torchaudio.__version__, cuda=torch.version.cuda)\n"
             "except Exception as e:\n"
             "    out['error'] = (type(e).__name__ + ': ' + str(e))[:300]\n"
             "print(json.dumps(out))")
    p = subprocess.run([str(vpy), "-c", probe], capture_output=True, text=True)
    try:
        cur = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        cur = {}
    good = cur.get("torch", "").split("+")[0] == TORCH_VERSION and cur.get("torchaudio", "").split("+")[0] == TORCH_VERSION
    if device == "cuda":
        good = good and str(cur.get("cuda") or "").startswith("12.8")
    elif device == "cpu":
        good = good and not cur.get("cuda")
    # installed (pip calls it satisfied) but it does not import: damaged files, unless the folder path is too long
    damaged = bool(cur.get("installed") and cur.get("error") and not too_long_hint(cur["error"]))
    if good and not reinstall:
        row("OK ", "torch", f"torch {cur['torch']} / torchaudio {cur['torchaudio']} (CUDA {cur.get('cuda') or '-'}, existing)")
    else:
        log(f"installing torch {want} + torchaudio {want} ({'CUDA 12.8' if device == 'cuda' else device})")
        idx = [] if device == "mac" else ["--index-url", TORCH_INDEX[device]]
        pip(vpy, *idx, f"torch=={want}", f"torchaudio=={want}")            # what is missing, or another build
        again = reinstall or damaged
        if again:      # --reinstall, or a damaged pair: put the same files in place again
            pip(vpy, *idx, "--force-reinstall", "--no-deps", f"torch=={want}", f"torchaudio=={want}")
        row("OK ", "torch", f"torch {want} / torchaudio {want} ({'installed again' if again else 'installed'})")
    cons = vpy.parent.parent / "openamika-constraints.txt"
    cons.write_text(f"torch=={want}\ntorchaudio=={want}\n", encoding="utf-8")
    return cons


def ensure_requirements(vpy: Path, engine: Path, cons: Path, reinstall: bool) -> None:
    req = engine / "requirements-tts.txt"
    stamp = vpy.parent.parent / "openamika-requirements.sha256"
    digest = hashlib.sha256(req.read_bytes() + cons.read_bytes()).hexdigest()
    if not reinstall and stamp.is_file() and stamp.read_text().strip() == digest:
        row("OK ", "packages", f"{req.name} (unchanged since last install)")
        return
    log(f"installing {req.name} (the torch pair stays pinned by {cons.name})")
    pip(vpy, "-r", str(req), "-c", str(cons))
    stamp.write_text(digest, encoding="utf-8")
    row("OK ", "packages", f"{req.name} (installed)")


# ---- upstream checkout + models -----------------------------------------------------------------
def git(*args: str, cwd: Path, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "-c", "advice.detachedHead=false", *args],
               cwd=cwd, capture=capture, check=check)


def tree_digest(z: zipfile.ZipFile) -> tuple[str, int]:
    """SHA-256 over the lines "<sha256 of file>  <path>\\n", sorted by path, of every file in a GitHub zip (its top
    folder stripped): the same value a git checkout of that commit gives over its tracked files."""
    files: dict[str, str] = {}
    for info in z.infolist():
        if info.is_dir():
            continue
        rel = info.filename.split("/", 1)[1] if "/" in info.filename else info.filename
        files[rel] = hashlib.sha256(z.read(info)).hexdigest()
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(f"{files[rel]}  {rel}\n".encode("utf-8"))
    return h.hexdigest(), len(files)


def check_tts_py(root: Path) -> None:
    """The extracted tree has the pinned commit's GPT_SoVITS/TTS_infer_pack/TTS.py (zip installs, which git cannot vouch for)."""
    rel, want = GPT_SOVITS_TTS_PY
    f = root / rel
    got = sha256_file(f) if f.is_file() else "missing"
    if got != want:
        raise IntegrityError(f"{f}: SHA-256 {got[:16]}… is not the one of GPT-SoVITS {GPT_SOVITS_COMMIT[:10]} "
                             f"({want[:16]}…)")


def git_pin(gsv: Path) -> None:
    """Shallow-fetch the pinned commit into gsv (an initialised repo, possibly from an interrupted run)."""
    if git("remote", "get-url", "origin", cwd=gsv, capture=True, check=False).returncode != 0:
        git("remote", "add", "origin", GPT_SOVITS_GIT, cwd=gsv)
    git("fetch", "--depth", "1", "origin", GPT_SOVITS_COMMIT, cwd=gsv)
    git("checkout", "--force", GPT_SOVITS_COMMIT, cwd=gsv)


def read_git_head(gsv: Path) -> str:
    """The commit a checkout is on, read from .git directly (git itself may not be on PATH): a detached HEAD or a
    branch ref, loose or packed. Same logic as main.py's upstream_commit."""
    git_dir = gsv / ".git"
    try:
        head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
        if head.startswith("ref:"):
            ref = head.split(":", 1)[1].strip()
            if (git_dir / ref).is_file():
                head = (git_dir / ref).read_text(encoding="utf-8").strip()
            elif (git_dir / "packed-refs").is_file():
                for line in (git_dir / "packed-refs").read_text(encoding="utf-8").splitlines():
                    if line.endswith(" " + ref):
                        head = line.split(" ", 1)[0]
                        break
        return head if re.fullmatch(r"[0-9a-f]{40}", head) else ""
    except OSError:
        return ""


def checkout_edits(gsv: Path, has_git: bool) -> str:
    """Check an existing checkout: TTS.py (the module main.py builds on) must be the pinned one; other tracked files
    with local edits are reported. Returns a note for the summary."""
    restore = f'`git -C "{gsv}" checkout -- .` restores it' if has_git else f"move {gsv} away and re-run"
    try:
        check_tts_py(gsv)
    except IntegrityError as e:
        raise IntegrityError(f"{e}: it was edited; {restore}") from e
    if not has_git:
        return "git not on PATH: commit read from .git, TTS.py verified"
    p = git("status", "--porcelain", "--untracked-files=no", cwd=gsv, capture=True, check=False)
    edited = [ln[3:].strip().strip('"') for ln in (p.stdout or "").splitlines() if len(ln) > 3] if p.returncode == 0 else []
    edited = [f for f in edited if f not in GPT_SOVITS_SELF_WRITTEN]
    if not edited:
        return "TTS.py verified, no local edits"
    log(f"WARNING: {len(edited)} tracked file(s) in {gsv} differ from commit {GPT_SOVITS_COMMIT[:10]}: "
        f"{', '.join(edited[:6])}{' ...' if len(edited) > 6 else ''}. `git -C \"{gsv}\" checkout -- .` restores them.")
    return f"TTS.py verified; {len(edited)} other file(s) edited locally, see the warning above"


def ensure_checkout(engine: Path) -> Path:
    gsv = engine / "GPT-SoVITS"
    marker = gsv / ".openamika-commit"
    has_git = shutil.which("git") is not None
    if (gsv / ".git").exists():
        if has_git:
            p = git("rev-parse", "HEAD", cwd=gsv, capture=True, check=False)
            head = p.stdout.strip() if p.returncode == 0 else ""
        else:
            head = read_git_head(gsv)
        if head == GPT_SOVITS_COMMIT:
            row("OK ", "GPT-SoVITS", f"{gsv} @ {head[:10]} (existing; {checkout_edits(gsv, has_git)})")
            return gsv
        if not has_git:
            raise SetupError(f"{gsv} is a git checkout at {head[:10] or 'an unknown commit'}, not the pinned "
                             f"{GPT_SOVITS_COMMIT[:10]}, and git is not on PATH: install git and re-run, or move the "
                             "folder away (the pinned commit is then downloaded as a zip)")
        log(f"GPT-SoVITS is at {head[:10] or 'nothing yet'}; fetching the pinned {GPT_SOVITS_COMMIT[:10]}")
        git_pin(gsv)
        row("OK ", "GPT-SoVITS", f"{gsv} @ {GPT_SOVITS_COMMIT[:10]} (updated)")
        return gsv
    if gsv.is_dir() and marker.is_file():
        if marker.read_text().strip() == GPT_SOVITS_COMMIT:
            try:
                check_tts_py(gsv)
            except IntegrityError as e:
                raise IntegrityError(f"{e}; move {gsv} away and re-run") from e
            row("OK ", "GPT-SoVITS", f"{gsv} @ {GPT_SOVITS_COMMIT[:10]} (existing, from zip; TTS.py verified)")
            return gsv
        raise SetupError(f"{gsv} is a different GPT-SoVITS snapshot; move it away and re-run")
    if gsv.exists() and any(gsv.iterdir()):
        raise SetupError(f"{gsv} exists but is not a pinned GPT-SoVITS checkout; move it away and re-run")
    if has_git:
        gsv.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=gsv)
        git_pin(gsv)
        how = "git, shallow"
    else:
        log("git not found; downloading the pinned commit as a zip from GitHub")
        downloads = engine / "downloads"
        tmp = downloads / f"GPT-SoVITS-{GPT_SOVITS_COMMIT}.zip"
        src = downloads / f"GPT-SoVITS-{GPT_SOVITS_COMMIT}"
        # GitHub builds the archive on request and does not promise stable bytes, so never continue an old .part;
        # the tree digest below checks the files inside instead
        fetch(GPT_SOVITS_ZIP.format(commit=GPT_SOVITS_COMMIT), tmp, None, None, resume=False)
        try:
            with zipfile.ZipFile(tmp) as z:
                digest, count = tree_digest(z)
                if digest != GPT_SOVITS_TREE_SHA256:
                    raise IntegrityError(f"{tmp.name}: its {count} files do not match the pinned GPT-SoVITS "
                                         f"{GPT_SOVITS_COMMIT[:10]} (tree SHA-256 {digest[:16]}…, expected "
                                         f"{GPT_SOVITS_TREE_SHA256[:16]}…); install git and re-run")
                safe_members(z.namelist(), downloads)
                shutil.rmtree(src, ignore_errors=True)    # left over from an interrupted run
                z.extractall(downloads)
            check_tts_py(src)                 # the unpacked tree, before it is moved into place
        except (zipfile.BadZipFile, IntegrityError) as e:
            tmp.unlink(missing_ok=True)      # a re-run downloads it again
            shutil.rmtree(src, ignore_errors=True)
            if isinstance(e, IntegrityError):
                raise
            raise SetupError(f"{tmp.name} is not a valid zip ({e}); re-run to download it again") from e
        if gsv.exists():
            shutil.copytree(src, gsv, dirs_exist_ok=True)
            shutil.rmtree(src)
        else:
            shutil.move(str(src), str(gsv))
        tmp.unlink(missing_ok=True)
        marker.write_text(GPT_SOVITS_COMMIT, encoding="utf-8")
        how = "zip"
    row("OK ", "GPT-SoVITS", f"{gsv} @ {GPT_SOVITS_COMMIT[:10]} (downloaded, {how})")
    return gsv


def ensure_pretrained(gsv: Path, ver: Verified) -> None:
    pm = gsv / "GPT_SoVITS" / "pretrained_models"
    states = []
    for rel, size, sha in PRETRAINED:
        url = f"{HF}/{PRETRAINED_REPO}/resolve/{PRETRAINED_REV}/{rel}"
        states.append(fetch(url, pm / rel, size, sha, ver, label=rel if size > 50e6 else None))
    total = sum(s for _, s, _ in PRETRAINED) / 1e9
    row("OK ", "pretrained models", f"HuBERT, RoBERTa, ERes2NetV2 sv ({total:.1f} GB, "
        f"{'downloaded' if 'downloaded' in states else 'verified'}) from {PRETRAINED_REPO}@{PRETRAINED_REV[:7]}")

    lid = pm / "fast_langdetect" / "lid.176.bin"
    st = fetch(LANGID[0], lid, LANGID[1], LANGID[2], ver)
    row("OK ", "language ID", f"fastText lid.176.bin ({st})")


def ensure_g2pw(engine: Path, gsv: Path, ver: Verified, keep: bool) -> None:
    text_dir = gsv / "GPT_SoVITS" / "text"
    onnx = text_dir / "G2PWModel" / G2PW_ONNX[0]
    needed = ["config.py", "char_bopomofo_dict.json", "bopomofo_to_pinyin_wo_tune_dict.json",
              "POLYPHONIC_CHARS.txt", "MONOPHONIC_CHARS.txt"]
    if ver.ok(onnx, G2PW_ONNX[1], G2PW_ONNX[2]) and all((onnx.parent / n).is_file() for n in needed):
        row("OK ", "G2PW", f"{onnx.parent} (verified)")
        return
    zpath = engine / "downloads" / G2PW_ZIP[0]
    fetch(f"{HF}/{G2PW_REPO}/resolve/{G2PW_REV}/{G2PW_ZIP[0]}", zpath, G2PW_ZIP[1], G2PW_ZIP[2], ver,
          label="G2PW model (zip)")
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        if not all(n.startswith("G2PWModel/") for n in names):
            raise SetupError("unexpected G2PWModel.zip layout")
        safe_members(names, text_dir)
        z.extractall(text_dir)
    if not ver.ok(onnx, G2PW_ONNX[1], G2PW_ONNX[2]):
        raise SetupError(f"{onnx} does not match the pinned SHA-256 after extraction")
    if not keep:
        zpath.unlink(missing_ok=True)
    row("OK ", "G2PW", f"{onnx.parent} (downloaded from {G2PW_REPO}@{G2PW_REV[:7]})")


def ensure_nltk(engine: Path, ver: Verified) -> None:
    base = engine / "nltk_data"
    for rel, size, sha in NLTK:
        dest = base / rel
        fetch(f"https://raw.githubusercontent.com/nltk/nltk_data/{NLTK_COMMIT}/packages/{rel}", dest, size, sha, ver)
        unpacked = dest.with_suffix("")
        done = unpacked / ".openamika-unpacked"      # written last, so an interrupted unzip is redone
        if not (done.is_file() and done.read_text(encoding="utf-8").strip() == sha):
            with zipfile.ZipFile(dest) as z:
                names = z.namelist()
                safe_members(names, dest.parent)
                if not all(n.startswith(unpacked.name + "/") for n in names):
                    raise SetupError(f"unexpected layout of {dest.name}")
                z.extractall(dest.parent)
            done.write_text(sha, encoding="utf-8")
    row("OK ", "nltk data", f"{base} (averaged_perceptron_tagger[_eng], cmudict)")


JA_DICT = r"""
import contextlib, io, os, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
gsv = sys.argv[1]
sys.path[:0] = [os.path.join(gsv, "GPT_SoVITS"), gsv]
os.chdir(gsv)                     # as main.py runs it: upstream may keep a copy of the dictionary under TEMP/ here
out = io.StringIO()
with contextlib.redirect_stdout(out):
    import text.japanese as ja    # builds ja_userdic/user.dict from userdict.csv when it is missing or stale
path = getattr(ja, "USERDIC_BIN_PATH", "")
print("OK" if path and os.path.isfile(path) else "MISSING", os.path.abspath(path) if path else "-")
"""


def ensure_ja_dict(vpy: Path, gsv: Path) -> None:
    """Let upstream's Japanese front-end build its user dictionary now (21 MB, about a second, ~100 progress lines on
    the console) instead of during the server's first start. Optional: the server builds it itself if needed."""
    try:
        p = subprocess.run([str(vpy), "-I", "-c", JA_DICT, str(gsv)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=600)
        out, err, rc = p.stdout or "", p.stderr or "", p.returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        out, err, rc = "", f"{type(e).__name__}: {e}", 1
    # the dictionary compiler prints its progress bar straight to stdout (C stdio); the result is the last OK/MISSING
    last = next((ln.strip() for ln in reversed(out.splitlines()) if ln.startswith(("OK ", "MISSING "))), "")
    path = Path(last[3:]) if last.startswith("OK ") else None
    if rc == 0 and path is not None and path.is_file():
        row("OK ", "Japanese dictionary", f"{path} ({path.stat().st_size / 1e6:.0f} MB)")
    else:
        why = last or (err.strip().splitlines() or ["no output"])[-1]
        row("-- ", "Japanese dictionary", f"not built ({why[:200]}); the server builds it on its first start")


# ---- ffmpeg -------------------------------------------------------------------------------------
def ffmpeg_info(exe: str) -> Optional[str]:
    try:
        p = subprocess.run([exe, "-hide_banner", "-encoders"], capture_output=True, text=True, timeout=30,
                           errors="replace")
        v = subprocess.run([exe, "-version"], capture_output=True, text=True, timeout=30, errors="replace")
        if p.returncode == 0 and v.returncode == 0:
            first = v.stdout.splitlines()[0] if v.stdout else "ffmpeg"
            return first + ("" if "libopus" in p.stdout else "  (WARNING: no libopus encoder)")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def linux_ffmpeg_asset(engine: Path) -> tuple[str, str, int, str]:
    """(file name, URL, size, SHA-256) of the newest release branch's static linux64 build in BtbN's "latest"
    release, from GitHub's asset list (one request instead of a separate checksum file)."""
    listing = engine / "downloads" / "ffmpeg-release.json"
    fetch(FFMPEG_LINUX_RELEASE, listing, None, None, headers={"Accept": "application/vnd.github+json"}, resume=False)
    try:
        assets = json.loads(listing.read_text(encoding="utf-8")).get("assets") or []
    except ValueError as e:
        raise SetupError(f"{FFMPEG_LINUX_RELEASE} did not return JSON: {e}") from e
    finally:
        listing.unlink(missing_ok=True)
    best: Optional[tuple[tuple[int, int], dict]] = None
    for a in assets:
        m = FFMPEG_LINUX_ASSET.fullmatch(str(a.get("name") or ""))
        if m and (best is None or (int(m[1]), int(m[2])) > best[0]):
            best = ((int(m[1]), int(m[2])), a)
    if best is None:
        raise SetupError(f"no ffmpeg-nX.Y-latest-linux64-gpl-X.Y.tar.xz in {FFMPEG_LINUX_RELEASE}")
    a = best[1]
    digest = str(a.get("digest") or "")
    if not digest.startswith("sha256:") or not str(a.get("size") or "").isdigit():
        raise SetupError(f"the release listing gives no SHA-256 for {a['name']}; install ffmpeg with your package "
                         "manager instead")
    return str(a["name"]), str(a["browser_download_url"]), int(a["size"]), digest.split(":", 1)[1].lower()


def download_ffmpeg(engine: Path, dest: Path, ver: Verified) -> Path:
    """Fetch and unpack the ffmpeg build for this platform (Windows or Linux x86_64) into dest; returns the archive."""
    if IS_WIN:
        url, size, sha = FFMPEG_WIN
        arc = engine / "downloads" / url.rsplit("/", 1)[1]
        fetch(url, arc, size, sha, ver, label="ffmpeg 8.0.1 essentials build (gyan.dev)")
        with zipfile.ZipFile(arc) as z:
            for n in z.namelist():
                leaf = n.rsplit("/", 1)[-1]
                if (leaf in ("ffmpeg.exe", "ffprobe.exe") and "/bin/" in n) or leaf == "LICENSE":
                    (dest / leaf).write_bytes(z.read(n))
        return arc
    arc: Optional[Path] = None
    for listing in (1, 2):
        name, url, size, sha = linux_ffmpeg_asset(engine)
        arc = engine / "downloads" / name
        log(f"ffmpeg static build {name} (BtbN, rolling release; checked against the SHA-256 GitHub lists for it)")
        try:
            fetch(url, arc, size, sha, label=name)
            break
        except IntegrityError:
            # BtbN re-publishes the release daily: between the listing and the download the file was replaced
            if listing == 2:
                raise
            log("  the build was re-published while downloading; reading the release listing again")
    assert arc is not None
    with tarfile.open(arc, "r:xz") as t:
        for m in t.getmembers():
            leaf = m.name.rsplit("/", 1)[-1]
            if m.isfile() and leaf in ("ffmpeg", "ffprobe") and "/bin/" in m.name:
                f = t.extractfile(m)
                if f is None:
                    raise SetupError(f"cannot read {m.name} from {arc.name}")
                (dest / leaf).write_bytes(f.read())
                (dest / leaf).chmod(0o755)
    return arc


def ensure_ffmpeg(engine: Path, ver: Verified, keep: bool) -> None:
    dest = engine / "ffmpeg"
    exe = dest / ("ffmpeg.exe" if IS_WIN else "ffmpeg")
    if exe.is_file() and (info := ffmpeg_info(str(exe))):
        row("OK ", "ffmpeg", f"{exe} ({info.split(' Copyright')[0]})")
        return
    system = shutil.which("ffmpeg")
    if not IS_WIN and system and (info := ffmpeg_info(system)) and "WARNING" not in info:
        row("OK ", "ffmpeg", f"{system} (system; {info.split(' Copyright')[0]})")
        return
    if not (IS_WIN or (sys.platform.startswith("linux") and platform.machine() in ("x86_64", "AMD64"))):
        hint = "brew install ffmpeg" if IS_MAC else "install ffmpeg with your package manager"
        row("-- ", "ffmpeg", f"not found: {hint} (only needed for Opus; WAV output works without it)")
        return
    dest.mkdir(parents=True, exist_ok=True)
    try:
        arc = download_ffmpeg(engine, dest, ver)
    except SetupError:
        raise
    except Exception as e:  # noqa: BLE001  (a broken archive or disk error: report it like any other ffmpeg failure)
        raise SetupError(f"ffmpeg download / unpack failed: {type(e).__name__}: {e}") from e
    if not keep:
        arc.unlink(missing_ok=True)
    info = ffmpeg_info(str(exe))
    if not info:
        raise SetupError(f"{exe} does not run")
    row("OK ", "ffmpeg", f"{exe} ({info.split(' Copyright')[0]}, downloaded)")


# ---- her voice and Live2D model (the Hugging Face repository MekaHime/MekaHime_Amika) ------------------------
def load_manifest(path: Path) -> dict:
    """The pinned file list of her repository (scripts/MekaHime_Amika.manifest.json):
    {"repo", "revision", "files": {path in the repository: (size, sha256)}, "paper_doll": {path: (size, sha256)}}.
    "paper_doll" holds live2d/Host/ (the paper doll), pinned at PAPER_DOLL_REV rather than at "revision"; it is empty
    in a list that has no such block."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        files = {str(p): (int(e[0]), str(e[1]).lower()) for p, e in data["files"].items()}
        repo, rev = str(data["repo"]), str(data["revision"])
        doll = {str(p): (int(e[0]), str(e[1]).lower()) for p, e in ((data.get("paper_doll") or {}).get("files") or {}).items()}
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
        raise SetupError(f"{path} cannot be read ({type(e).__name__}: {e}); restore it (git checkout -- scripts) and "
                         "run this script again") from e
    if (repo, rev) != (VOICE_REPO, VOICE_REV):
        raise SetupError(f"{path} lists {repo}@{rev[:8]}, but this script pins {VOICE_REPO}@{VOICE_REV[:8]}: the two "
                         "must be updated together")
    stray = [p for p in doll if not p.startswith(PAPER_DOLL_PATH + "/")]
    if stray:
        raise SetupError(f"{path}: the paper_doll block lists {stray[0]}, which is not under {PAPER_DOLL_PATH}/; restore "
                         "it (git checkout -- scripts) and run this script again")
    return {"repo": repo, "revision": rev, "files": files, "paper_doll": doll}


def model_files(files: dict, path: str) -> dict:
    """One Live2D model folder of the repository (`path`, e.g. live2d/Amika) from a file list {path: (size, sha256)},
    keyed by the path inside that folder, in install order: its .model3.json last (the file that makes the folder count
    as a model on the Use page), so an interrupted download never looks complete, and the paper doll's banks.json
    ("role": "agent") is in place before it."""
    prefix = path + "/"
    found = {p[len(prefix):]: e for p, e in files.items() if p.startswith(prefix)}
    return dict(sorted(found.items(), key=lambda kv: (kv[0].endswith(".model3.json"), kv[0])))


def split_assets(files: dict) -> tuple[dict, dict]:
    """(her voice, her Live2D model) from a repository file list {path: (size, sha256)}. The voice is every file
    outside live2d/ except the repository's own .gitattributes, keyed by its path under Speakers/<voice id>/; the model
    is live2d/Amika/, keyed by its path under avatar/models/Amika/. Each comes in install order: the file that makes
    the folder count as installed (character.json, the .model3.json) is last, so an interrupted download never looks
    complete to the voice server or the Use page. (The paper doll, live2d/Host/, is paper_doll_files'.)"""
    voice = {p: e for p, e in files.items() if not p.startswith("live2d/") and p not in REPO_ONLY}
    return (dict(sorted(voice.items(), key=lambda kv: (kv[0] == "character.json", kv[0]))),
            model_files(files, AVATAR_PATH))


def hf_token(explicit: Optional[str]) -> tuple[Optional[str], str]:
    """(token, where it came from) for her repository, or (None, ""): --hf-token, HF_TOKEN (or the older
    HUGGING_FACE_HUB_TOKEN), else the file `hf auth login` saves (HF_TOKEN_PATH, or "token" in HF_HOME, by default
    ~/.cache/huggingface), unless HF_HUB_DISABLE_IMPLICIT_TOKEN is set. Only needed while the repository is private.
    It is sent to huggingface.co only (never to the CDN it redirects to, nor to a mirror HF_ENDPOINT names: see
    token_goes_to) and is never printed or written."""
    if explicit and explicit.strip():
        return explicit.strip(), "--hf-token"
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if os.environ.get(var, "").strip():
            return os.environ[var].strip(), var
    if os.environ.get("HF_HUB_DISABLE_IMPLICIT_TOKEN", "").strip().lower() in ("1", "true", "yes", "on"):
        return None, ""
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    try:
        saved = Path(os.environ.get("HF_TOKEN_PATH") or os.path.join(home, "token")).read_text(encoding="utf-8").strip()
    except OSError:
        return None, ""
    return (saved, "`hf auth login`") if saved else (None, "")


def revision_files(args: argparse.Namespace) -> dict:
    """{path: (None, None)} for every file of another revision of her repository, from the Hub's API (--voice-revision
    other than the pinned one): such files are not pinned, so they are not hash-checked."""
    url = f"{HF}/api/models/{args.repo}/revision/{urllib.parse.quote(args.revision)}"
    req = urllib.request.Request(url, headers=UA)
    if args.token:
        req.add_unredirected_header("Authorization", "Bearer " + args.token)
    try:
        with OPENER.open(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise HTTPStatusError(url, e.code, str(e.reason), e.headers.get("X-Error-Code") or "") from e
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError) as e:
        raise SetupError(f"{url}: {e}") from e
    return {str(s["rfilename"]): (None, None) for s in data.get("siblings") or [] if s.get("rfilename")}


def asset_files(args: argparse.Namespace, manifest: Optional[dict]) -> tuple[dict, dict]:
    """(voice files, Live2D model files) to install: the pinned manifest at the pinned revision, else the listing of
    the revision asked for."""
    if args.revision != VOICE_REV:
        return split_assets(revision_files(args))
    if manifest is None:
        raise SetupError("the pinned file list (scripts/MekaHime_Amika.manifest.json) could not be read; see its row")
    return split_assets(manifest["files"])


def paper_doll_files(args: argparse.Namespace, manifest: Optional[dict]) -> tuple[dict, Optional[str]]:
    """(the paper doll's files, keyed by their path under avatar/models/Host, the revision they come from). At the
    pinned revision: the manifest's "paper_doll" pins at PAPER_DOLL_REV, which is None while that placeholder is empty
    (nothing may be downloaded then). With another --voice-revision: the listing of that revision (not pinned)."""
    if args.revision != VOICE_REV:
        return model_files(revision_files(args), PAPER_DOLL_PATH), args.revision
    if manifest is None:
        raise SetupError("the pinned file list (scripts/MekaHime_Amika.manifest.json) could not be read; see its row")
    return model_files(manifest.get("paper_doll") or {}, PAPER_DOLL_PATH), (PAPER_DOLL_REV.strip() or None)


def copy_pinned(src: Path, dest: Path, size: Optional[int], sha: Optional[str], ver: Verified) -> None:
    """Copy one file of a local folder (--from-dir) into place through a .part file, checked like a download."""
    if not src.is_file():
        raise SetupError(f"{src} is missing")
    if size is not None and src.stat().st_size != size:
        raise IntegrityError(f"{src} has {src.stat().st_size:,} bytes; the pinned file has {size:,}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    try:
        shutil.copyfile(src, part)
    except OSError as e:
        part.unlink(missing_ok=True)
        if e.errno == errno.ENOSPC:
            raise SetupError(f"{dest.parent}: the disk is full") from e
        raise SetupError(f"copying {src} failed: {e}") from e
    if sha:
        got = sha256_file(part)
        if got != sha:
            part.unlink(missing_ok=True)
            raise IntegrityError(f"{src}: SHA-256 {got[:16]}… is not the pinned {sha[:16]}…")
    os.replace(part, dest)
    if size is not None and sha:
        ver.record(dest, size, sha)


def install_files(what: str, files: dict, dest: Path, repo_path: Callable[[str], str], args: argparse.Namespace,
                  ver: Verified, keep: tuple[str, ...] = (), revision: Optional[str] = None) -> dict:
    """Bring every file of `files` ({path under dest: (size, sha256), or (None, None) when not pinned}) into dest. A
    file already there with its pinned size and SHA-256 stays; any other one comes from Hugging Face (or HF_ENDPOINT)
    at `revision` (default args.revision), or from the --from-dir folder, and is checked before it takes its place
    (through a .part file, so an interrupted download resumes). A file named in `keep` (her banks.json, which the Setup
    page edits) stays as it is once it was edited after the install; while it is still the copy this script installed,
    a newer pin replaces it. With --verify nothing is fetched: what is missing or different is only listed.
    Returns {"present", "fetched", "kept": counts, "bad": [paths]}."""
    force = args.update_voice if what == "her voice" else args.update_avatar
    rev = revision or args.revision
    stats: dict[str, Any] = {"present": 0, "fetched": 0, "kept": 0, "bad": []}
    total = sum(size or 0 for size, _ in files.values())
    done, t_last = 0, time.time()
    for i, (rel, (size, sha)) in enumerate(files.items(), 1):
        target = dest / Path(*rel.split("/"))
        as_pinned = ver.ok(target, size, sha) if size is not None and sha else target.is_file()
        if as_pinned and (not force or rel in keep):
            stats["present"] += 1
        elif rel in keep and target.is_file() and not ver.as_installed(target):
            stats["kept"] += 1                             # edited after the install (Setup page): hers to keep
        elif args.verify:
            stats["bad"].append(rel)
        else:
            src_rel = repo_path(rel)
            if args.from_dir:
                copy_pinned(Path(args.from_dir).expanduser().resolve() / Path(*src_rel.split("/")), target, size, sha,
                            ver)
            else:
                if rev not in args.announced:              # once per revision (the paper doll may have its own)
                    args.announced.add(rev)
                    where = f" (HF_ENDPOINT {HF})" if HF != HF_SITE else ""
                    log(f"downloading {what} from {HF_SITE}/{args.repo} at revision {rev[:12]}{where}" +
                        (f"; using your Hugging Face token (from {args.token_source})" if args.token else ""))
                url = f"{HF}/{args.repo}/resolve/{rev}/{urllib.parse.quote(src_rel)}"
                fetch(url, target, size, sha, None, auth=args.token)
                if size is not None and sha:
                    ver.record(target, size, sha)        # fetch() checked it
            if rel in keep:
                ver.installed(target)                    # an unedited copy may be replaced by a later pin
            stats["fetched"] += 1
        done += size or 0
        if time.time() - t_last > 10 and i < len(files) and not args.verify:
            log(f"  {what}: {i} of {len(files)} files" + (f" ({done / 1e6:,.0f} / {total / 1e6:,.0f} MB)" if total else ""))
            t_last = time.time()
    return stats


def hf_refused(e: HTTPStatusError, args: argparse.Namespace, revision: Optional[str] = None) -> str:
    """The summary row for a download Hugging Face refused: what it means and what to do, per status."""
    repo, page, rev = args.repo, f"{HF_SITE}/{args.repo}", revision or args.revision
    tok = f"your Hugging Face token (from {args.token_source})"
    set_it = '$env:HF_TOKEN = "hf_..."' if IS_WIN else 'export HF_TOKEN=hf_...'
    if e.code == 401 and not args.token:
        return (f"Hugging Face refused the download (HTTP 401): {repo} is not public yet. Until it is, set HF_TOKEN to a "
                f"read token of an account that can see it ({set_it} in this window), then run this script again")
    if e.code == 401:
        return (f"Hugging Face did not accept {tok} (HTTP 401): it is wrong or has expired. Set HF_TOKEN to a valid read "
                f"token (or remove it once {repo} is public), then run this script again")
    if e.code == 403 and e.error_code == "GatedRepo":
        return (f"{repo} is gated (HTTP 403): accept its terms on {page} while logged in, set HF_TOKEN to a read token of "
                "that account, then run this script again")
    if e.code in (403, 404) and args.token and e.error_code in ("", "RepoNotFound", "GatedRepo"):
        return (f"the account of {tok} cannot read {repo} (HTTP {e.code}): use a read token of an account that has "
                "access, then run this script again")
    if e.code == 404 and e.error_code == "RepoNotFound":
        return (f"Hugging Face does not show {repo} (HTTP 404): while it is private, set HF_TOKEN to a read token of an "
                f"account that can see it ({set_it}), then run this script again")
    if e.code == 404:
        name = urllib.parse.unquote(e.url.rsplit("/", 1)[-1])
        return (f"Hugging Face has no {name} at revision {rev[:8]} of {repo} (HTTP 404"
                f"{', ' + e.error_code if e.error_code else ''}): update OpenAmika (git pull) and run this script again")
    return f"Hugging Face refused {urllib.parse.unquote(e.url)} (HTTP {e.code}); run this script again later"


def fetch_assets(what: str, files: dict, dest: Path, repo_path: Callable[[str], str], args: argparse.Namespace,
                 ver: Verified, keep: tuple[str, ...] = (), revision: Optional[str] = None) -> dict:
    """install_files with its failures worded for the summary row. A refusal or a network failure is also said at
    once: the voice server install that follows takes minutes before the summary repeats it."""
    try:
        return install_files(what, files, dest, repo_path, args, ver, keep, revision)
    except HTTPStatusError as e:
        if args.from_dir:
            raise
        msg = hf_refused(e, args, revision)
        log(f"!! {what}: {msg}")
        raise SetupError(msg) from e
    except IntegrityError as e:
        text = str(e).rstrip()
        text += "" if text.endswith(".") else "."
        if args.from_dir:
            raise IntegrityError(f"{text} Files already in place are kept") from e
        raise IntegrityError(f"{text} Files already in place are kept. Run this script again; if it repeats, update "
                             "OpenAmika (git pull)") from e
    except SetupError as e:
        if args.from_dir or "the disk is full" in str(e):
            raise
        msg = (f"{e}. Check the internet connection (if huggingface.co cannot be reached from here, set HF_ENDPOINT to "
               "a Hugging Face mirror) and run this script again (files already downloaded are kept and the rest "
               "resumes)")
        log(f"!! {what}: {msg}")
        raise SetupError(msg) from e


def adapter_tags() -> Optional[tuple[list[str], set[str]]]:
    """(V1_IDS, the targets of DEFAULT_MAP) read from speech/voice_adapter.py without importing it; None when that file
    is not there (an engine installed outside an OpenAmika checkout) or cannot be read."""
    import ast
    try:
        tree = ast.parse(VOICE_ADAPTER.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return None
    found: dict[str, Any] = {}
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        for t in targets:
            if isinstance(t, ast.Name) and t.id in ("V1_IDS", "DEFAULT_MAP") and node.value is not None:
                try:
                    found[t.id] = ast.literal_eval(node.value)
                except ValueError:
                    return None
    if not isinstance(found.get("V1_IDS"), list) or not isinstance(found.get("DEFAULT_MAP"), dict):
        return None
    return [str(x) for x in found["V1_IDS"]], {str(v) for v in found["DEFAULT_MAP"].values()}


def check_voice(d: Path) -> tuple[bool, str]:
    """(usable, detail) for a voice folder: character.json, the weights it names, references/emotions.json and the
    clips it names, and whether every tag OpenAmika's voice adapter can send has a clip."""
    try:
        meta = json.loads((d / "character.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False, "character.json missing"
    cid = meta.get("character_id") or d.name
    weights = [str(meta.get(key) or default) for key, default in (("llm_model", f"{cid}.ckpt"), ("vocoder_model", f"{cid}.pth"))]
    for name in weights:
        if not (d / name).is_file():
            return False, f"{name} missing"
    try:
        table = json.loads((d / "references" / "emotions.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False, "references/emotions.json missing"
    tags = {k: v for k, v in table.items() if not k.startswith("_") and isinstance(v, dict)}
    with_clip = {k.strip().lower() for k, v in tags.items() if (d / "references" / str(v.get("audio", ""))).is_file()}
    if not with_clip:
        return False, "no reference clips"
    notes = [f"{len(with_clip)}/{len(tags)} emotion tags with a clip"]
    wanted = adapter_tags()
    if wanted is not None:
        ids, defaults = wanted
        missing = [t for t in ids if t not in with_clip]
        if not missing:
            notes.append(f"all {len(ids)} tags OpenAmika's voice adapter can send have one")
        else:
            gone = [t for t in missing if t in defaults]
            notes.append(f"{len(missing)} of the {len(ids)} tags OpenAmika's voice adapter can send have no clip and fall back to neutral1 ({', '.join(missing[:8])}{' ...' if len(missing) > 8 else ''})"
                         + (f", {len(gone)} of them in its default map" if gone else ""))
    return True, "; ".join(notes)


def check_avatar(d: Path) -> tuple[bool, str]:
    """(usable, detail) for a Live2D model folder: its .model3.json and every file it names."""
    models = sorted(d.glob("*.model3.json")) if d.is_dir() else []
    if not models:
        return False, "no .model3.json"
    try:
        refs = json.loads(models[0].read_text(encoding="utf-8-sig")).get("FileReferences") or {}
        need = [refs.get("Moc"), refs.get("Physics"), *(refs.get("Textures") or []),
                *(e.get("File") for e in refs.get("Expressions") or []),
                *(m.get("File") for group in (refs.get("Motions") or {}).values() for m in group)]
    except (OSError, ValueError, AttributeError) as e:
        return False, f"{models[0].name} cannot be read ({e})"
    missing = [str(n) for n in need if n and not (d / str(n)).is_file()]
    if missing:
        return False, f"{len(missing)} file(s) the model names are missing ({', '.join(missing[:4])})"
    return True, (f"{models[0].name}, {len(list(d.glob('*.motion3.json')))} motions, "
                  f"{len(list(d.glob('*.exp3.json')))} expressions")


def check_paper_doll(d: Path) -> tuple[bool, str]:
    """check_avatar, plus the "role": "agent" in its banks.json: without it the doll would count as a second model of
    hers (offered in her model picker) instead of standing in for her helpers."""
    good, why = check_avatar(d)
    if not good:
        return good, why
    try:
        role = (json.loads((d / "banks.json").read_text(encoding="utf-8-sig")).get("config") or {}).get("role")
    except (OSError, ValueError, AttributeError):
        role = None
    if role != "agent":
        return False, (f"{why}; but its banks.json does not say \"role\": \"agent\", so the Use page would offer it as "
                       "a model of hers: delete that banks.json and run this script again to get the pinned one back")
    return True, why


LICENSE_URL = f"{HF_SITE}/{VOICE_REPO}/blob/main/LICENSE"


def ask_voice_license() -> bool:
    """Show the license of her voice, her Live2D model and the paper doll in short on an interactive console and ask
    once."""
    print(f"\n[voice] Amika's voice, her Live2D model and the paper doll that stands in for her helpers ({HF_SITE}/{VOICE_REPO}) are free under MekaHime's personal-use license:\n"
          "          - personal use only, and you must be 18 or older (social media and fan merch up to US$1,000: see its creator rules)\n"
          "          - no redistribution, re-hosting or resale of her voice, her Live2D model, the paper doll or their files\n"
          "          - no training, fine-tuning or distilling other models on them\n"
          "          - credit MekaHime visibly when you post videos or streams with her\n"
          f"          full text: {LICENSE_URL}\n", flush=True)
    try:
        answer = input("[voice] type yes to accept and download her voice, her Live2D model and the paper doll (anything else skips them for now): ")
    except (EOFError, KeyboardInterrupt):
        print(flush=True)
        return False
    return answer.strip().lower() in ("yes", "y")


def not_accepted(args: argparse.Namespace) -> str:
    how = ("Run this script again in a console and type yes when it asks" if not args.console else
           "Run this script again and type yes when it asks")
    return (f"not downloaded: her license was not accepted (one license covers her voice, her Live2D model and the "
            f"paper doll). {how}, or pass --accept-voice-license once you have read it ({LICENSE_URL})")


def files_note(stats: dict, files: dict, args: argparse.Namespace, revision: Optional[str] = None) -> str:
    """What happened to the files, for the summary row (revision: where they came from, default args.revision)."""
    rev = revision or args.revision
    pinned = all(sha for _, sha in files.values())
    origin = (f"from {args.from_dir}" if args.from_dir else f"from {args.repo}@{rev[:8]}")
    checked = (f"{len(files)} files verified" if pinned else f"{len(files)} files of revision {rev[:8]}, "
               "not pinned: not hash-checked")
    if stats["fetched"]:
        verb = "copied" if args.from_dir else "downloaded"
        got = f"{verb} {stats['fetched']} file(s) {origin}"
        return f"{got}; {checked}" + ("; your banks.json kept" if stats["kept"] else "")
    return f"existing; {checked} against {args.repo}@{rev[:8]}" + ("; your banks.json kept" if stats["kept"] else "")


def verify_failed(dest: Path, bad: list[str], files: dict) -> str:
    """The --verify row for files that are missing or differ from the pins."""
    if len(bad) == len(files):
        return (f"{dest}: not installed yet. Run this script without --verify (it asks you to accept her license "
                "first)")
    return (f"{dest}: {len(bad)} of {len(files)} files missing or not the pinned ones ({', '.join(bad[:4])}"
            f"{' ...' if len(bad) > 4 else ''}). Run this script without --verify to download them again")


def ensure_voice(engine: Path, args: argparse.Namespace, ver: Verified, manifest: Optional[dict]) -> None:
    """Her voice into Speakers/MekaHime_Amika: every file of her repository outside live2d/, checked file by file
    against the pinned manifest. Needs no venv: only the standard library."""
    dest = engine / "Speakers" / VOICE_ID
    name = f"voice {VOICE_ID}"
    if args.voice_from:
        src = Path(args.voice_from).expanduser().resolve()
        good, why = check_voice(src)
        if not good:
            raise SetupError(f"--voice-from {src}: {why}")
        try:
            shutil.copytree(src, dest, dirs_exist_ok=True, ignore=shutil.ignore_patterns("live2d", ".cache", ".git*"))
        except (OSError, shutil.Error) as e:
            raise SetupError(f"copying the voice from {src} to {dest} failed: {e}") from e
        good, why = check_voice(dest)
        row("OK " if good else "!! ", name, f"{dest} (copied from {src}, not checked against the pins; {why})")
        return
    installed = (dest / "character.json").is_file()
    if args.skip_voice:
        good, why = check_voice(dest)
        row("OK " if good else "-- ", name, f"{dest} ({why}; not checked: --skip-voice)" if good else
            "skipped (--skip-voice): she answers in text only until her voice is installed (run this script again "
            "without --skip-voice)")
        return
    if not (installed or args.accept_voice_license or args.verify):
        row("!! ", name, not_accepted(args))
        return
    files, _ = asset_files(args, manifest)
    stats = fetch_assets("her voice", files, dest, lambda p: p, args, ver)
    good, why = check_voice(dest)
    if args.verify and stats["bad"]:
        row("!! ", name, verify_failed(dest, stats["bad"], files))
        return
    row("OK " if good else "!! ", name, f"{dest} ({files_note(stats, files, args)}; {why})")


def ensure_avatar(engine: Path, args: argparse.Namespace, ver: Verified, manifest: Optional[dict]) -> None:
    """Her Live2D model (live2d/Amika in the same repository, same license) into avatar/models/Amika, where the Use
    page finds it. A banks.json there (her emotion banks, edited on the Setup page) is never overwritten."""
    dest = Path(args.avatar_dir).expanduser().resolve()
    name = f"Live2D model {AVATAR_ID}"
    installed = dest.is_dir() and any(dest.glob("*.model3.json"))
    if args.skip_avatar:
        good, why = check_avatar(dest)
        row("OK " if good else "-- ", name, f"{dest} ({why}; not checked: --skip-avatar)" if good else
            "skipped (--skip-avatar): the Use page shows \"No Live2D model yet\" until a model is in avatar/models/")
        return
    if not (installed or args.accept_voice_license or args.verify):
        row("!! ", name, not_accepted(args))
        return
    _, files = asset_files(args, manifest)
    stats = fetch_assets("her Live2D model", files, dest, lambda p: f"{AVATAR_PATH}/{p}", args, ver, keep=("banks.json",))
    good, why = check_avatar(dest)
    if args.verify and stats["bad"]:
        row("!! ", name, verify_failed(dest, stats["bad"], files))
        return
    row("OK " if good else "!! ", name, f"{dest} ({files_note(stats, files, args)}; {why})")


DOLL_ROLE = "stands in for her helpers on the Use page while a task agent is on"


def ensure_paper_doll(engine: Path, args: argparse.Namespace, ver: Verified, manifest: Optional[dict]) -> None:
    """The paper doll (live2d/Host in the same repository, same license) into avatar/models/Host. The Use page seats
    it beside her whenever a task agent (Hermes Agent, nanoMuse) is switched on on the Tools page, and its speech
    bubbles carry the helper's side of the exchange. Checked file by file like her model; an edited banks.json is
    kept. Its files are pinned at PAPER_DOLL_REV: while that placeholder is empty nothing is downloaded (a doll already
    in place, or one from --from-dir, is still checked against the pins). A --from-dir copy without live2d/Host/ (made
    before the doll was added) installs her voice and her model as always: the doll's row is then a note, not a
    failure."""
    dest = Path(args.paper_doll_dir).expanduser().resolve()
    name = f"paper doll {PAPER_DOLL_ID}"
    installed = dest.is_dir() and any(dest.glob("*.model3.json"))
    if args.skip_paper_doll:
        good, why = check_paper_doll(dest)
        row("OK " if good else "-- ", name, f"{dest} ({why}; not checked: --skip-paper-doll)" if good else
            "skipped (--skip-paper-doll): her helpers (Hermes Agent, nanoMuse) have no stand-in on her stage and no "
            "speech bubbles until a model whose banks.json says \"role\": \"agent\" is in avatar/models/")
        return
    files, revision = paper_doll_files(args, manifest)
    if not files:
        row("-- ", name, (f"{args.repo}@{args.revision[:8]} has no {PAPER_DOLL_PATH}/" if args.revision != VOICE_REV else
                          f"the pinned file list has no {PAPER_DOLL_PATH}/ (update OpenAmika: git pull)") +
            ": her helpers have no stand-in on her stage")
        return
    unpinned = (f"this OpenAmika does not pin the revision of {args.repo} that adds {PAPER_DOLL_PATH}/ yet "
                "(PAPER_DOLL_REV in scripts/setup_tts.py is empty). Her helpers work without it; they only have no "
                "stand-in on her stage. Update OpenAmika (git pull) and run this script again later")
    # Nothing to bring it from in this run: PAPER_DOLL_REV is not set yet (it cannot be downloaded), or the --from-dir
    # copy has no live2d/Host/ (one made before the doll was added). Then a doll in place is only checked, and a missing
    # one is a note, not a failure: her voice and her model install all the same.
    if args.from_dir and not from_dir_has_doll(args):
        folder = Path(args.from_dir).expanduser().resolve()
        unreachable = (f"{folder} has no {PAPER_DOLL_PATH}/ (a copy of {args.repo} from before the doll was added). Her "
                       "helpers work without it; they only have no stand-in on her stage. " +
                       ("Run this script without --from-dir to download it" if revision else
                        "This OpenAmika cannot download it yet either (PAPER_DOLL_REV in scripts/setup_tts.py is "
                        "empty): update OpenAmika (git pull) and run this script again later"))
    elif revision is None and not args.from_dir:
        unreachable = unpinned
    else:
        unreachable = ""
    if unreachable and not installed:
        row("-- ", name, f"not {'copied' if args.from_dir else 'downloaded'}: {unreachable}")
        return
    if not (installed or args.accept_voice_license or args.verify or unreachable):
        row("!! ", name, not_accepted(args))
        return
    # unreachable: check, never fetch; and not as --update-avatar either, which counts every intact file as one to fetch
    probe = argparse.Namespace(**{**vars(args), "verify": True, "update_avatar": False}) if unreachable else args
    stats = fetch_assets("the paper doll", files, dest, lambda p: f"{PAPER_DOLL_PATH}/{p}", probe, ver,
                         keep=("banks.json",), revision=revision)
    good, why = check_paper_doll(dest)
    if stats["bad"]:
        if unreachable:
            row("-- ", name, f"{dest}: {len(stats['bad'])} of {len(files)} files missing or not the pinned ones "
                             f"({', '.join(stats['bad'][:4])}{' ...' if len(stats['bad']) > 4 else ''}); they cannot be "
                             f"repaired {'from that folder' if args.from_dir else 'from Hugging Face'}: {unreachable}")
        else:
            row("!! ", name, verify_failed(dest, stats["bad"], files))
        return
    note = (files_note(stats, files, args, revision) if revision or stats["fetched"] else
            f"existing; {len(files)} files verified against the pinned list" +
            ("; your banks.json kept" if stats["kept"] else ""))
    if unreachable and args.update_avatar:
        note += ("; not copied again (--update-avatar): that folder has no paper doll" if args.from_dir else
                 "; not downloaded again (--update-avatar): PAPER_DOLL_REV is not set yet")
    row("OK " if good else "!! ", name, f"{dest} ({note}; {why}; {DOLL_ROLE})")


def from_dir_has_doll(args: argparse.Namespace) -> bool:
    """Does the --from-dir copy hold the paper doll (live2d/Host/)? A copy made before the doll was added does not."""
    return bool(args.from_dir) and (Path(args.from_dir).expanduser().resolve() /
                                    Path(*PAPER_DOLL_PATH.split("/"))).is_dir()


def write_manifest_from(folder: Path, out: Path, revision: str) -> int:
    """--write-manifest: the pinned file list of a local copy of her repository at `revision` (maintainers, after
    publishing a new revision): every file's size and SHA-256, written to `out`. The paper doll (live2d/Host/) goes
    into the "paper_doll" block; a copy without it keeps the block that is there (the doll stays at PAPER_DOLL_REV)."""
    folder = folder.expanduser().resolve()
    files = {p.relative_to(folder).as_posix(): p for p in sorted(folder.rglob("*"))
             if p.is_file() and not any(part.startswith(".") and part != ".gitattributes"
                                        for part in p.relative_to(folder).parts)}
    if "character.json" not in files or not any(f.startswith(AVATAR_PATH + "/") for f in files):
        raise SetupError(f"{folder} does not look like her repository (character.json and {AVATAR_PATH}/ expected)")
    doll_prefix = PAPER_DOLL_PATH + "/"

    def entry(rel: str, size: int, sha: str) -> str:
        return f'{json.dumps(rel, ensure_ascii=False)}: [{size}, "{sha}"]'

    lines = ["    " + entry(rel, p.stat().st_size, sha256_file(p))
             for rel, p in sorted(files.items()) if not rel.startswith(doll_prefix)]
    old = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    old_doll = old.get("paper_doll") if isinstance(old.get("paper_doll"), dict) else {}
    doll = {rel: (p.stat().st_size, sha256_file(p)) for rel, p in files.items() if rel.startswith(doll_prefix)}
    kept = not doll
    if kept:
        doll = {str(rel): (int(e[0]), str(e[1])) for rel, e in (old_doll.get("files") or {}).items()}
    doll_lines = ["      " + entry(rel, size, sha) for rel, (size, sha) in sorted(doll.items())]
    text = ("{\n" + f'  "_readme": {json.dumps(old.get("_readme", ""), ensure_ascii=False)},\n'
            f'  "repo": {json.dumps(VOICE_REPO)},\n  "revision": {json.dumps(revision)},\n  "files": {{\n'
            + ",\n".join(lines) + "\n  },\n"
            f'  "paper_doll": {{\n    "_readme": {json.dumps(old_doll.get("_readme", ""), ensure_ascii=False)},\n'
            + ('    "files": {\n' + ",\n".join(doll_lines) + "\n    }\n" if doll_lines else '    "files": {}\n')
            + "  }\n}\n")
    out.write_text(text, encoding="utf-8", newline="\n")
    me = Path(__file__).name
    print(f"{out}: {len(lines)} files of {VOICE_REPO}@{revision[:8]}. Set VOICE_REV in {me} to {revision} as well.")
    if not kept:
        print(f"  and the paper doll's {len(doll)} files ({PAPER_DOLL_PATH}/): set PAPER_DOLL_REV in {me} to {revision} too.")
    elif doll:
        print(f"  The paper doll's {len(doll)} pins were kept: this copy has no {PAPER_DOLL_PATH}/ (PAPER_DOLL_REV stays).")
    return 0


# ---- verification -------------------------------------------------------------------------------
IMPORT_PROBE = r"""
import json, importlib, sys
mods = ["torch", "torchaudio", "transformers", "onnxruntime", "pyopenjtalk", "nltk", "jieba", "opencc", "g2p_en",
        "pypinyin", "cn2an", "librosa", "soundfile", "pytorch_lightning", "peft", "socketio", "aiohttp", "split_lang",
        "fast_langdetect", "x_transformers", "matplotlib", "resampy", "ffmpeg", "ToJyutping", "g2pk2"]
out, bad, dists = {}, {}, {}
for m in mods:
    try:
        mod = importlib.import_module(m)
        out[m] = getattr(mod, "__version__", "ok")
    except Exception as e:
        bad[m] = f"{type(e).__name__}: {e}"[:200]
if bad:                  # installed but not importable: the distributions (name==version) to put in place again
    try:
        import importlib.metadata as md
        for dist in md.distributions():
            files = {str(f).replace("\\", "/") for f in (dist.files or [])}
            for m in bad:
                if m + "/__init__.py" in files or any(f.startswith(m + ".") and "/" not in f[len(m):] for f in files):
                    dists.setdefault(m, []).append(dist.metadata["Name"] + "==" + dist.version)
    except Exception:
        pass
cuda = False
if "torch" in out:
    import torch
    cuda = torch.cuda.is_available()
out["cuda"] = cuda
out["gpu"] = torch.cuda.get_device_name(0) if cuda else ""
print(json.dumps({"ok": out, "bad": bad, "dists": dists}))
"""


def verify_imports(vpy: Path) -> dict:
    p = subprocess.run([str(vpy), "-I", "-c", IMPORT_PROBE], capture_output=True, text=True, errors="replace")
    try:
        res = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise SetupError(f"import check failed:\n{p.stderr[-1500:]}")
    bad = {k: v for k, v in res["bad"].items() if k not in ("g2pk2",)}   # Korean is optional
    if bad:
        detail = "; ".join(f"{k}: {v}" for k, v in bad.items())
        hint = too_long_hint(detail)
        # installed but damaged (pip calls them satisfied); torch and torchaudio come from the PyTorch index (--reinstall)
        redo = sorted({d for k in bad for d in (res.get("dists") or {}).get(k, [])
                       if not d.lower().startswith(("torch==", "torchaudio=="))})
        if hint:
            detail += f" — {hint}"
        elif redo:
            detail += (f" — installed but damaged: {vpy} -m pip install --force-reinstall --no-deps {' '.join(redo)}, "
                       "then run this script again")
        else:
            detail += " — run this script again with --reinstall; if it repeats, see the pip output above"
        row("!! ", "imports", detail)
    else:
        ok = res["ok"]
        gpu = f"CUDA OK on {ok['gpu']}" if ok.get("cuda") else "no CUDA (CPU)"
        row("OK ", "imports", f"{len(ok) - 2} packages import; torch {ok.get('torch')}; {gpu}")
    return res


SELF_TEST = r"""
import asyncio, os, socket, subprocess, sys, time, urllib.request, uuid
import socketio
engine, py = sys.argv[1], sys.argv[2]
with socket.socket() as s:
    s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
log = open(os.path.join(engine, "cache", "self-test.log"), "wb")
proc = subprocess.Popen([py, "main.py", "--port", str(port)], cwd=engine, stdout=log, stderr=subprocess.STDOUT)
t0 = time.time()
try:
    while time.time() - t0 < 600:
        try:
            if urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=3).status == 200: break
        except Exception: pass
        if proc.poll() is not None: sys.exit(f"server exited ({proc.returncode}); see cache/self-test.log")
        time.sleep(1)
    else: sys.exit("server did not become ready in 10 min")
    ready = time.time() - t0
    async def go():
        sio = socketio.AsyncClient()
        done, out = asyncio.Event(), {}
        @sio.on("audio_ready")
        async def _a(d):
            out.setdefault("audio", b""); out["audio"] += d["audio"]; out["meta"] = d
            if d.get("is_final"): done.set()
        @sio.on("error")
        async def _e(d): out["error"] = d.get("error"); done.set()
        await sio.connect(f"http://127.0.0.1:{port}", transports=["websocket"])
        t = time.time()
        await sio.emit("tts_request_gateway", {"task_id": str(uuid.uuid4()), "turn_id": "self-test-0",
            "text": "【happy2】.おかえりなさい。今日もおつかれさま。", "character_id": "MekaHime_Amika",
            "audio_format": "wav", "language": "Japanese"})
        await asyncio.wait_for(done.wait(), 120)
        await sio.disconnect()
        return out, time.time() - t
    out, dt = asyncio.run(go())
    if "error" in out: sys.exit("synthesis error: " + out["error"])
    m = out["meta"]
    path = os.path.join(engine, "cache", "self-test.wav")
    open(path, "wb").write(out["audio"])
    print(f"ready after {ready:.0f} s; {m['audio_duration']:.2f} s of audio in {dt:.2f} s -> {path}")
finally:
    proc.terminate()
"""


def self_test(engine: Path, vpy: Path) -> None:
    (engine / "cache").mkdir(exist_ok=True)
    p = subprocess.run([str(vpy), "-I", "-c", SELF_TEST, str(engine), str(vpy)], capture_output=True, text=True,
                       errors="replace")
    msg = (p.stdout.strip() or p.stderr.strip()[-600:]).splitlines()[-1] if (p.stdout or p.stderr) else "no output"
    row("OK " if p.returncode == 0 else "!! ", "self-test", msg)


# ---- main ---------------------------------------------------------------------------------------
def sync_engine_files(engine: Path) -> None:
    if engine.resolve() == SOURCE_ENGINE.resolve():
        return
    engine.mkdir(parents=True, exist_ok=True)
    for name in ENGINE_FILES:
        src = SOURCE_ENGINE / name
        if src.is_file() and (not (engine / name).is_file() or (engine / name).read_bytes() != src.read_bytes()):
            shutil.copy2(src, engine / name)
            log(f"copied {name} -> {engine}")


def long_paths_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
            return int(winreg.QueryValueEx(k, "LongPathsEnabled")[0]) == 1
    except (ImportError, OSError, ValueError):
        return False


def check_launcher(engine: Path) -> None:
    """OpenAmika's launcher starts this server from settings.json "services.tts" and sends tts_character (the voice
    adapter: config/voice_map.json "voice") as character_id. Report whether they point here; never edits them."""
    settings = ROOT / "settings.json"
    block = {"enabled": True, "command": [str(venv_python(engine).relative_to(ROOT)) if engine.is_relative_to(ROOT)
                                         else str(venv_python(engine)), "main.py", "--port", "8002", "--host", "127.0.0.1"],
             "cwd": str(engine.relative_to(ROOT)) if engine.is_relative_to(ROOT) else str(engine),
             "health": "http://127.0.0.1:8002/ping", "timeout_s": 240}
    hint = (f'settings.json needs  "tts_character": "{VOICE_ID}"  and  "services": {{"tts": '
            f'{json.dumps(block)}}}  (settings.example.json has both)')
    if not settings.is_file():
        row("-- ", "launcher", "settings.json not found yet: the core setup (powershell -ExecutionPolicy Bypass -File "
            "scripts\\setup_windows.ps1) creates it, or copy settings.example.json to settings.json; its \"services.tts\" "
            "block starts this server on port 8002")
        return
    try:
        cfg = json.loads(settings.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        row("!! ", "launcher", f"settings.json cannot be read ({e})")
        return
    tts = (cfg.get("services") or {}).get("tts") or {}
    cmd = [str(c) for c in (tts.get("command") or [])]
    exe = Path(cmd[0]) if cmd else None
    if exe is not None and not exe.is_absolute():
        exe = ROOT / exe
    cwd = Path(str(tts.get("cwd") or "."))
    cwd = cwd if cwd.is_absolute() else ROOT / cwd
    problems = []
    if not tts or tts.get("enabled", True) is False:
        problems.append("services.tts is missing or disabled")
    elif exe is None or exe.resolve() != venv_python(engine).resolve() or "main.py" not in cmd or cwd.resolve() != engine.resolve():
        problems.append(f"services.tts runs {' '.join(cmd) or 'nothing'} in {cwd}, not this server")
    if cfg.get("tts_character") != VOICE_ID:
        problems.append(f"tts_character is {cfg.get('tts_character')!r}, not {VOICE_ID!r}")
    vmap = ROOT / "config" / "voice_map.json"
    try:
        voice = json.loads(vmap.read_text(encoding="utf-8-sig")).get("voice") if vmap.is_file() else None
    except (OSError, ValueError):
        voice = None
    if voice and voice != VOICE_ID:
        problems.append(f"config/voice_map.json speaks through {voice!r} (Setup -> Voice: set the voice to {VOICE_ID})")
    if problems:
        row("-- ", "launcher", "; ".join(problems) + ". " + hint)
    else:
        row("OK ", "launcher", f"settings.json starts this server (services.tts, port from tts_url) with voice {VOICE_ID}")


def write_install_json(engine: Path, vpy: Path, device: str, probe: dict, args: argparse.Namespace) -> None:
    """install.json: what this install holds (commits, revisions, torch build) and when her license was accepted."""
    try:
        before = json.loads((engine / "install.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        before = {}
    info = {
        "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "complete": not any(m.strip() == "!!" for m, _, _ in ROWS),   # every step so far succeeded
        "gpt_sovits": {"repo": GPT_SOVITS_GIT, "commit": GPT_SOVITS_COMMIT},
        "torch": {"version": TORCH_VERSION, "variant": device, "cuda_available": bool(probe.get("ok", {}).get("cuda"))},
        "python": ".".join(map(str, py_version([str(vpy)]) or ())),
        "pretrained": {"repo": PRETRAINED_REPO, "revision": PRETRAINED_REV},
        "g2pw": {"repo": G2PW_REPO, "revision": G2PW_REV},
        "nltk_data": NLTK_COMMIT,
        "voice": {"repo": VOICE_REPO, "id": VOICE_ID, "revision": args.revision},
        "avatar": {"repo": VOICE_REPO, "path": AVATAR_PATH, "id": AVATAR_ID, "revision": args.revision},
        "paper_doll": {"repo": VOICE_REPO, "path": PAPER_DOLL_PATH, "id": PAPER_DOLL_ID,
                       "revision": (args.revision if args.revision != VOICE_REV else PAPER_DOLL_REV.strip()) or None},
        "license": ({"accepted": args.license_how, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "terms": LICENSE_URL}
                    if args.license_how else before.get("license")),
    }
    (engine / "install.json").write_text(json.dumps(info, indent=2), encoding="utf-8")


def verify_engine(engine: Path, ver: Verified) -> None:
    """--verify: the voice server's own files, without installing anything: its venv, GPT-SoVITS's TTS.py, and the
    pretrained, language-ID and G2PW models by size and SHA-256 (hashes are cached, so a second check is quick)."""
    problems = []
    vpy = venv_python(engine)
    if not vpy.is_file():
        problems.append(f"{vpy.relative_to(engine)} is missing")
    gsv = engine / "GPT-SoVITS"
    try:
        check_tts_py(gsv)
    except IntegrityError:
        problems.append(f"GPT-SoVITS is missing or not commit {GPT_SOVITS_COMMIT[:10]}")
    pm = gsv / "GPT_SoVITS" / "pretrained_models"
    models = [(pm / rel, size, sha) for rel, size, sha in PRETRAINED]
    models += [(pm / "fast_langdetect" / "lid.176.bin", LANGID[1], LANGID[2]),
               (gsv / "GPT_SoVITS" / "text" / "G2PWModel" / G2PW_ONNX[0], G2PW_ONNX[1], G2PW_ONNX[2])]
    bad = [f.name for f, size, sha in models if not ver.ok(f, size, sha)]
    if bad:
        problems.append(f"{len(bad)} model file(s) missing or changed ({', '.join(bad[:3])}{' ...' if len(bad) > 3 else ''})")
    if problems:
        raise SetupError(f"{engine}: " + "; ".join(problems) + ". Run this script without --verify to install or repair it")
    row("OK ", "voice server", f"{engine} (venv, GPT-SoVITS {GPT_SOVITS_COMMIT[:10]}, {len(models)} model files verified)")


class Steps:
    """Runs the install steps one by one. A step that raises (or reports a !! row itself) is marked failed and
    the run goes on; a later step that needs a failed one is skipped with a -- row instead of running."""

    def __init__(self) -> None:
        self.failed: list[str] = []

    def run(self, name: str, fn: Callable[..., Any], *args: Any, needs: tuple[str, ...] = ()) -> Any:
        blocked = [n for n in needs if n in self.failed]
        if blocked:
            row("-- ", name, f"skipped: needs {', '.join(blocked)}, which did not finish (see above)")
            self.failed.append(name)
            return None
        rows_before = len(ROWS)
        try:
            result = fn(*args)
        except SetupError as e:
            row("!! ", name, str(e))
        except Exception as e:  # noqa: BLE001  (an unexpected failure is reported like any other)
            traceback.print_exc()
            row("!! ", name, f"unexpected {type(e).__name__}: {e} (traceback above)")
        else:
            if any(m.strip() == "!!" for m, _, _ in ROWS[rows_before:]):
                self.failed.append(name)
            return result
        self.failed.append(name)
        return None


def and_list(items: list[str]) -> str:
    """"a", "a and b", "a, b and c" (non-empty)."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def optional_ffmpeg(engine: Path, ver: Verified, keep: bool) -> None:
    try:
        ensure_ffmpeg(engine, ver, keep)
    except Exception as e:  # noqa: BLE001  (optional component: report it, keep going)
        row("-- ", "ffmpeg", f"{e} (only needed for Opus output; WAV works without it)")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Install Amika's voice, her Live2D model and the paper doll that stands in for "
                                             "her helpers (from Hugging Face) and the OpenAmika voice server (a MekaHime "
                                             "build of GPT-SoVITS)")
    ap.add_argument("--engine-dir", type=Path, default=SOURCE_ENGINE, help="default: vendor/tts-engine")
    ap.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto",
                    help="torch build: auto = CUDA 12.8 when an NVIDIA GPU is visible (Windows/Linux), else CPU")
    ap.add_argument("--cpu", action="store_true", help="same as --device cpu")
    ap.add_argument("--python", default=None, help="Python 3.11 (or 3.12) interpreter for the venv (default: the first "
                                                     "3.11 found: this one, py -3.11, python3.11; then 3.12)")
    ap.add_argument("--accept-voice-license", action="store_true",
                    help="accept the license of Amika's voice, her Live2D model and the paper doll (personal use, 18+) "
                         "without being asked")
    ap.add_argument("--verify", action="store_true",
                    help="check her voice, her Live2D model and the paper doll file by file (size + SHA-256) and the "
                         "voice server's files; download and install nothing")
    ap.add_argument("--assets-only", action="store_true",
                    help="only her voice, her Live2D model and the paper doll: skip the voice server install (torch, "
                         "GPT-SoVITS, models)")
    ap.add_argument("--from-dir", default=None,
                    help="take her voice, her Live2D model and the paper doll from a local folder laid out like the "
                         "Hugging Face repository (offline installs); every file is still checked against the pinned list")
    ap.add_argument("--skip-voice", action="store_true", help="do not install Amika's voice")
    ap.add_argument("--voice-from", default=None,
                    help="copy a voice folder you already have (character.json, weights, references/) instead")
    ap.add_argument("--update-voice", action="store_true", help="download every file of her voice again")
    ap.add_argument("--voice-revision", default=VOICE_REV,
                    help=f"revision of {VOICE_REPO} (default: the pinned {VOICE_REV[:8]}, whose files are all checked "
                         "by SHA-256; other revisions are not)")
    ap.add_argument("--skip-avatar", action="store_true", help="do not install Amika's Live2D model")
    ap.add_argument("--update-avatar", action="store_true",
                    help="download her Live2D model and the paper doll again (a banks.json you edited is kept)")
    ap.add_argument("--avatar-dir", default=str(ROOT / "avatar" / "models" / "Amika"),
                    help="where her Live2D model goes (default: avatar/models/Amika)")
    ap.add_argument("--skip-paper-doll", action="store_true",
                    help="do not install the paper doll that stands in for her helpers (Hermes Agent, nanoMuse)")
    ap.add_argument("--paper-doll-dir", default=str(ROOT / "avatar" / "models" / PAPER_DOLL_ID),
                    help=f"where the paper doll goes (default: avatar/models/{PAPER_DOLL_ID})")
    ap.add_argument("--hf-token", default=None,
                    help="Hugging Face token; prefer the HF_TOKEN environment variable or `hf auth login` (a command "
                         "line is visible to other programs). Needed only while her repository is private")
    ap.add_argument("--skip-ffmpeg", action="store_true")
    ap.add_argument("--reinstall", action="store_true", help="re-run the pip steps even if nothing changed")
    ap.add_argument("--keep-downloads", action="store_true", help="keep the zip archives in downloads/")
    ap.add_argument("--self-test", action="store_true", help="start the server once and synthesize a line")
    ap.add_argument("--manifest", type=Path, default=MANIFEST, help=argparse.SUPPRESS)     # tests: another pinned list
    ap.add_argument("--write-manifest", type=Path, default=None, metavar="FOLDER",
                    help="maintainers: write the pinned list (scripts/MekaHime_Amika.manifest.json) from a local copy of "
                         "her repository at --voice-revision, then exit")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:  # file names and messages can be non-ASCII; never die on a cp1252 console or log file
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    if args.write_manifest:
        if args.voice_revision == VOICE_REV:
            ap.error("--write-manifest needs --voice-revision <the new commit of the repository>")
        return write_manifest_from(args.write_manifest, args.manifest, args.voice_revision)
    ROWS.clear()
    args.repo, args.revision = VOICE_REPO, args.voice_revision
    args.console = sys.stdin.isatty()
    args.announced = set()          # revisions whose first download was announced
    args.license_how = ""

    engine = args.engine_dir.expanduser().resolve()
    mode = " (--verify: nothing is installed)" if args.verify else " (--assets-only)" if args.assets_only else ""
    log(f"OpenAmika voice setup -> {engine}{mode}  ({platform.system()} {platform.machine()}, Python {platform.python_version()})")
    free = disk_free_gb(engine)
    if not args.verify and free is not None and free < (2 if args.assets_only else 12):
        log(f"WARNING: only {free:.0f} GB free; " + ("her voice, her Live2D model and the paper doll need about 0.5 GB"
                                                  if args.assets_only else "a full install needs about 9 GB"))
    warning = "" if args.verify else long_folder_warning(ROOT if engine.is_relative_to(ROOT) else engine)
    if warning:
        log(warning)
    voice_dir = engine / "Speakers" / VOICE_ID
    avatar_dir = Path(args.avatar_dir).expanduser()
    doll_dir = Path(args.paper_doll_dir).expanduser()
    voice_missing = args.update_voice or not (voice_dir / "character.json").is_file()
    avatar_missing = args.update_avatar or not any(avatar_dir.glob("*.model3.json"))
    # the paper doll counts only when it can come in this run (its revision is pinned, or a local copy that has it, or
    # another revision asked for): an install that pulls a newer OpenAmika is then asked again, since the license
    # covers it too
    doll_reachable = (from_dir_has_doll(args) if args.from_dir else
                      bool(PAPER_DOLL_REV.strip()) or args.voice_revision != VOICE_REV)
    doll_missing = args.update_avatar or not any(doll_dir.glob("*.model3.json"))
    wanted = ((voice_missing and not (args.skip_voice or args.voice_from)) or (avatar_missing and not args.skip_avatar)
              or (doll_missing and doll_reachable and not args.skip_paper_doll))
    if wanted and not args.verify:
        if args.accept_voice_license:
            args.license_how = "--accept-voice-license"
        elif args.console:
            args.accept_voice_license = ask_voice_license()   # asked first, so the long install can run unattended
            args.license_how = "typed yes" if args.accept_voice_license else ""
    args.token, args.token_source = (None, "") if (args.verify or args.from_dir) else hf_token(args.hf_token)
    if args.token and not token_goes_to(HF):
        log(f"HF_ENDPOINT is {HF}: your Hugging Face token (from {args.token_source}) is not sent to a mirror, which "
            "serves public files only")
        args.token, args.token_source = None, ""
    t0 = time.time()
    rc = 0
    steps = Steps()
    try:
        if not (args.verify or args.assets_only):
            steps.run("engine files", sync_engine_files, engine)
        ver = Verified(engine / ".openamika-verified.json")
        manifest = None
        if args.revision == VOICE_REV and not (args.skip_voice and args.skip_avatar and args.skip_paper_doll):
            manifest = steps.run("pinned file list", load_manifest, args.manifest)
        # her voice, her Live2D model and the paper doll first: only the standard library, so they never wait for (or
        # fail with) torch
        steps.run(f"voice {VOICE_ID}", ensure_voice, engine, args, ver, manifest)
        steps.run(f"Live2D model {AVATAR_ID}", ensure_avatar, engine, args, ver, manifest)
        steps.run(f"paper doll {PAPER_DOLL_ID}", ensure_paper_doll, engine, args, ver, manifest)
        if args.assets_only:
            pass
        elif args.verify:
            steps.run("voice server", verify_engine, engine, ver)
            check_launcher(engine)
        else:
            device = pick_device(args)
            log(f"torch build: {'CUDA 12.8' if device == 'cuda' else 'CPU + Apple MPS' if device == 'mac' else 'CPU'}")
            # the venv chain: each step needs the one before it
            vpy = steps.run("venv", ensure_venv, engine, args.python)
            cons = steps.run("torch", ensure_torch, vpy, device, args.reinstall, needs=("venv",))
            steps.run("packages", ensure_requirements, vpy, engine, cons, args.reinstall,
                      needs=("engine files", "venv", "torch"))
            # downloads that only need the standard library: they run even when the venv chain failed
            gsv = steps.run("GPT-SoVITS", ensure_checkout, engine)
            steps.run("pretrained models", ensure_pretrained, gsv, ver, needs=("GPT-SoVITS",))
            steps.run("G2PW", ensure_g2pw, engine, gsv, ver, args.keep_downloads, needs=("GPT-SoVITS",))
            steps.run("nltk data", ensure_nltk, engine, ver)
            if args.skip_ffmpeg:
                row("-- ", "ffmpeg", "skipped (--skip-ffmpeg; WAV output works without it)")
            else:
                optional_ffmpeg(engine, ver, args.keep_downloads)
            probe = steps.run("imports", verify_imports, vpy, needs=("venv", "torch", "packages"))
            steps.run("Japanese dictionary", ensure_ja_dict, vpy, gsv, needs=("venv", "packages", "GPT-SoVITS"))
            if vpy is not None:
                steps.run("install record", write_install_json, engine, vpy, device, probe or {}, args)
            check_launcher(engine)
            if args.self_test:
                if any(m.strip() == "!!" for m, _, _ in ROWS):
                    row("-- ", "self-test", "skipped: fix the !! lines first")
                else:
                    steps.run("self-test", self_test, engine, vpy)
    except KeyboardInterrupt:
        row("!! ", "interrupted", "Ctrl-C (run this script again to resume; finished downloads are kept)")
        rc = 130

    width = max((len(n) for _, n, _ in ROWS), default=10)
    print("\n" + "=" * 78)
    print(f"OpenAmika voice setup summary ({time.time() - t0:.0f} s)")
    for mark, name, detail in ROWS:
        print(f"  {mark}{name.ljust(width)}  {detail}")
    bad = rc != 0 or any(m.strip() == "!!" for m, _, _ in ROWS)
    parts = [label for key, label in ((f"voice {VOICE_ID}", "her voice"), (f"Live2D model {AVATAR_ID}", "her Live2D model"),
                                      (f"paper doll {PAPER_DOLL_ID}", "the paper doll"))
             if any(m.strip() == "OK" and n == key for m, n, _ in ROWS)]
    print("=" * 78)
    brain = Path("envs/brain/Scripts/python.exe" if IS_WIN else "envs/brain/bin/python")
    check = f"{brain if (ROOT / brain).is_file() else '<brain python>'} launch.py --check"
    if bad:
        print("Fix the !! lines above and run this script again (finished steps are skipped)." if not args.verify else
              "Fix the !! lines above: run this script without --verify (finished files are kept).")
    elif args.verify:
        checked = parts + ([] if args.assets_only else ["the voice server"])
        print(f"Verified: {and_list(checked)} {'is' if len(checked) == 1 else 'are'} complete." if checked else
              "Verified: nothing to check (everything was skipped).")
    elif args.assets_only:
        print(f"Done: {and_list(parts)} {'is' if len(parts) == 1 else 'are'} in place." if parts else "Done.")
    elif IS_WIN:
        print("Done. Next:  .\\Start_OpenAmika.bat   (or double-click it: her voice server starts with the rest; the page "
              "opens at http://localhost:53000)")
        print(f"Check everything first, without starting anything:  {check}")
    else:
        print(f"Done. Next:  {check}   then   <brain python> launch.py")
    if not bad and not args.verify and not args.assets_only:
        print(f"Run the voice server alone:  {venv_python(engine)} {engine / 'main.py'} --port 8002")
    return rc or (1 if bad else 0)


if __name__ == "__main__":
    raise SystemExit(main())
