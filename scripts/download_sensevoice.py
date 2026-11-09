#!/usr/bin/env python3
"""Download the SenseVoiceSmall speech-recognition model into speech/models/ (~940 MB in total).

    python scripts\\download_sensevoice.py            # download what is missing, verify all (scripts/setup_core.py runs it)
    python scripts\\download_sensevoice.py --verify   # check the files, download nothing

Standard library only. Every file is pinned to the SHA-256 of the official iic/SenseVoiceSmall release
(FunAudioLLM), fetched from ModelScope first and Hugging Face as a fallback (Hugging Face does not carry
tokens.json). A file already present with the right hash is kept; a partial download resumes from a
.part file only when the server supports ranges, otherwise it restarts. The model files are under the
FunASR Model Open Source License Agreement and are not part of this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "speech" / "models"

# name -> (size in bytes, sha256), from the iic/SenseVoiceSmall release (ModelScope listing, 2026-11)
FILES = {
    "model.pt": (936291369, "833ca2dcfdf8ec91bd4f31cfac36d6124e0c459074d5e909aec9cabe6204a3ea"),
    "config.yaml": (1855, "f71e239ba36705564b5bf2d2ffd07eece07b8e3f2bbf6d2c99d8df856339ac19"),
    "configuration.json": (396, "02810a7f8e9e8aee10370a265f7e799728ce25b4c00cdbf4602b303ee395a38e"),
    "am.mvn": (11203, "29b3c740a2c0cfc6b308126d31d7f265fa2be74f3bb095cd2f143ea970896ae5"),
    "chn_jpn_yue_eng_ko_spectok.bpe.model": (377341, "aa87f86064c3730d799ddf7af3c04659151102cba548bce325cf06ba4da4e6a8"),
    "tokens.json": (352064, "a2594fc1474e78973149cba8cd1f603ebed8c39c7decb470631f66e70ce58e97"),
}
SOURCES = (
    "https://www.modelscope.cn/models/iic/SenseVoiceSmall/resolve/master/{name}",
    "https://huggingface.co/FunAudioLLM/SenseVoiceSmall/resolve/main/{name}",
)
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def is_good(path: Path, size: int, sha: str) -> bool:
    return path.is_file() and path.stat().st_size == size and sha256_of(path) == sha


def progress(done: int, size: int, rate: float) -> str:
    """'   412 / 937 MB  43%  8.1 MB/s  525 MB left, about 1 min'"""
    speed = f"{rate / 1e6:.1f} MB/s" if rate >= 1e5 else f"{rate / 1e3:.0f} KB/s"
    left = max(0, size - done)
    eta = left / rate if rate > 0 else 0
    when = (f", about {max(1, round(eta / 60))} min" if eta < 5400 else f", about {eta / 3600:.1f} h") if left and rate else ""
    return f"{done / 1e6:7.0f} / {size / 1e6:.0f} MB  {done * 100 // size:3d}%  {speed}  {left / 1e6:,.0f} MB left{when}"


def fetch(url: str, part: Path, size: int) -> None:
    """Download url into part (resuming when the server honours Range: ModelScope and Hugging Face both do);
    raises on any failure. A large file shows its progress, speed and what is left."""
    have = part.stat().st_size if part.exists() else 0
    if have > size:
        part.unlink()
        have = 0
    request = urllib.request.Request(url, headers={"User-Agent": "OpenAmika-setup/1.0"})
    if have:
        request.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(request, timeout=60) as response:
        if have and response.status != 206:      # no range support: start over
            have = 0
        if have:
            print(f"    continuing at {have / 1e6:,.0f} MB (an earlier run stopped there)")
        mode = "ab" if have else "wb"
        done, last = have, 0.0
        t0, first = time.monotonic(), have
        with part.open(mode) as out:
            while True:
                block = response.read(CHUNK)
                if not block:
                    break
                out.write(block)
                done += len(block)
                now = time.monotonic()
                if size > 10 * CHUNK and now - last > 0.5:
                    last = now
                    rate = (done - first) / max(1e-6, now - t0)
                    sys.stdout.write("\r    " + progress(done, size, rate) + "   ")
                    sys.stdout.flush()
    if size > 10 * CHUNK:
        sys.stdout.write("\n")


def download(name: str, size: int, sha: str) -> bool:
    target = DEST / name
    part = DEST / (name + ".part")
    if is_good(part, size, sha):                  # a finished download that was never renamed
        part.replace(target)
        return True
    for template in SOURCES:
        url = template.format(name=name)
        if name == "tokens.json" and "huggingface.co" in url:
            continue                              # not published on Hugging Face
        for attempt in (1, 2):
            try:
                print(f"  downloading {name} from {url.split('/')[2]}" + (" (retry)" if attempt > 1 else ""))
                fetch(url, part, size)
            except urllib.error.HTTPError as error:
                print(f"    failed: HTTP {error.code}")
                if error.code == 416:             # the .part cannot be resumed: start it over
                    part.unlink(missing_ok=True)
                    continue
                if 400 <= error.code < 500 and error.code not in (408, 429):
                    break                         # this source does not have it: try the next one
                continue
            except (urllib.error.URLError, OSError, TimeoutError) as error:
                print(f"    failed: {type(error).__name__}: {error}")
                continue
            if part.stat().st_size == size and sha256_of(part) == sha:
                part.replace(target)
                return True
            print("    checksum mismatch: discarding the download")
            part.unlink(missing_ok=True)
    return False


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:  # never die on a cp1252 console or a redirected log
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    parser = argparse.ArgumentParser(description="Download / verify SenseVoiceSmall into speech/models/")
    parser.add_argument("--verify", action="store_true", help="only check the files, download nothing")
    args = parser.parse_args()
    DEST.mkdir(parents=True, exist_ok=True)
    print(f"SenseVoiceSmall -> {DEST}")
    failed = []
    for name, (size, sha) in FILES.items():
        target = DEST / name
        if is_good(target, size, sha):
            print(f"  ok  {name}")
            continue
        if args.verify:
            print(f"  !!  {name} " + ("has the wrong size or checksum" if target.exists() else "is missing"))
            failed.append(name)
            continue
        if target.exists():
            print(f"  {name} is present but does not match the release: downloading it again")
        if not download(name, size, sha):
            failed.append(name)
    if failed:
        print("\nNot ready: " + ", ".join(failed) + ".\nCheck your connection and run this script again (finished files are kept),"
              "\nor download the files by hand from https://www.modelscope.cn/models/iic/SenseVoiceSmall into speech/models/.")
        return 1
    print("\nready: speech recognition model in place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
