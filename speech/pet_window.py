# Copyright (c) 2026 MekaHime Inc.
# SPDX-License-Identifier: MIT
"""Her desktop pet window, opened and closed from the web UI: the "Desktop pet" button on the Use page.

The window itself is pet.py (repo root): the Use page with ?pet=1 in a frameless, see-through, always-on-top
pywebview window. pet.py runs in the brain environment's Python, where pywebview is an optional install
(brain/requirements-pet.txt). This module runs inside the speech server (speech/api.py: GET /api/pet and
POST /api/pet/open, /api/pet/close, /api/pet/install), which starts that Python, waits until her page is alive in the
window, and can ask the window to close.

How the two processes find each other: pet.py holds a named Windows event for as long as its window lives
(event_name() here, instance_name() there: the same name, made from the folder OpenAmika is in), and makes a second
one, "<name>-ready", when her page in the window has asked for its hand-over. The first event existing means "her
window is open"; setting it means "close now". No port and no file: Windows drops both events with the process, so
nothing stale is left behind after a crash.

Standard library only: the speech environment has no pywebview and needs none.
"""
from __future__ import annotations

import ctypes
import hashlib
import ipaddress
import json
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PET = ROOT / 'pet.py'
REQUIREMENTS = ROOT / 'brain' / 'requirements-pet.txt'
LOG = ROOT / 'logs' / 'pet.log'
INSTALL_LOG = ROOT / 'logs' / 'pet-install.log'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)

SYNCHRONIZE, EVENT_MODIFY_STATE = 0x00100000, 0x0002
ERROR_FILE_NOT_FOUND, ERROR_ACCESS_DENIED = 2, 5
READY = '-ready'                 # pet.py makes "<event_name()>-ready" when her page in the window is alive

LOCAL_NAMES = frozenset({'localhost', '127.0.0.1', '::1'})
# a tunnel, a reverse proxy or Tailscale Serve also arrives from 127.0.0.1; each names the real caller in one of these
FORWARDED = ('x-forwarded-for', 'x-forwarded-host', 'x-forwarded-proto', 'forwarded', 'x-real-ip',
             'tailscale-user-login')
RECHECK_S = 10.0                 # "pywebview is missing" is asked again after this long; "it is there" is kept
CHECK = 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("webview") else 3)'

_installed = {}                  # python path -> (verdict, when it was checked)
_child = None                    # the pet.py process this server started (None: none, or she was opened another way)
_lock = threading.Lock()
_k32 = None


# ── who may ask ─────────────────────────────────────────────────────────────────────────────────────────────────
def is_local(client_host, headers) -> bool:
    """True when the request comes from this PC itself, straight to the server: only then may a page open a window on
    this desktop. Three things must hold. The caller's address is loopback. Nothing forwarded the request (FORWARDED).
    And the page was addressed by a local name: a web site that points its own domain at 127.0.0.1 (DNS rebinding)
    still sends its domain in Host."""
    try:
        address = ipaddress.ip_address(str(client_host or '').split('%')[0])
    except ValueError:
        return False
    if not (getattr(address, 'ipv4_mapped', None) or address).is_loopback:
        return False
    if any(headers.get(name) for name in FORWARDED):
        return False
    try:
        name = urlsplit('//' + str(headers.get('host') or '')).hostname
    except ValueError:
        return False
    return (name or '').lower() in LOCAL_NAMES


# ── which Python, and does it have pywebview ────────────────────────────────────────────────────────────────────
def pet_python(env=None, root=ROOT) -> Path:
    """The Python her window runs in. The launcher names its own (AMIKA_PET_PYTHON: launch.py runs in the brain
    environment, and `launch.py --pet` looks for pywebview there too); without the launcher it is settings.json's
    "brain_python", else the default environment."""
    env = os.environ if env is None else env
    named = str(env.get('AMIKA_PET_PYTHON') or '').strip()
    if named:
        return Path(named)
    root = Path(root)
    try:
        settings = json.loads((root / 'settings.json').read_text(encoding='utf-8-sig'))
        named = str(settings.get('brain_python') or '').strip() if isinstance(settings, dict) else ''
    except (OSError, ValueError):
        named = ''
    if named:
        path = Path(named)
        return path if path.is_absolute() else root / path
    return root / 'envs' / 'brain' / 'Scripts' / 'python.exe'


def has_pywebview(python, fresh=False) -> bool:
    """Whether `python` can import pywebview (asked of that Python itself: it is not this one). A yes is kept; a no
    is asked again after RECHECK_S seconds, or at once with fresh=True (after an install)."""
    key = str(python)
    with _lock:
        known = _installed.get(key)
    if known and not fresh and (known[0] or time.monotonic() - known[1] < RECHECK_S):
        return known[0]
    try:
        verdict = subprocess.run([key, '-c', CHECK], cwd=str(ROOT), stdin=subprocess.DEVNULL, capture_output=True,
                                 timeout=30, creationflags=NO_WINDOW).returncode == 0
    except (OSError, subprocess.SubprocessError):
        verdict = False
    with _lock:
        _installed[key] = (verdict, time.monotonic())
    return verdict


def forget_pywebview(python=None) -> None:
    """Ask again next time (her window said it has no pywebview after all)."""
    with _lock:
        if python is None:
            _installed.clear()
        else:
            _installed.pop(str(python), None)


# ── the named event ─────────────────────────────────────────────────────────────────────────────────────────────
def event_name(root=ROOT) -> str:
    """The name of the event pet.py holds while her window is open (pet.py instance_name(): keep the two the same).
    One per OpenAmika folder, so two installs on one PC do not see each other's window; "Local" keeps it inside
    this Windows session."""
    key = os.path.normcase(str(Path(root).resolve()))
    return r'Local\OpenAmika-pet-' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]


def _kernel32():
    global _k32
    if _k32 is None:
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.OpenEventW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
        k32.OpenEventW.restype = wintypes.HANDLE
        k32.SetEvent.argtypes = (wintypes.HANDLE,)
        k32.SetEvent.restype = wintypes.BOOL
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        k32.CloseHandle.restype = wintypes.BOOL
        _k32 = k32
    return _k32


def running(name=None) -> bool:
    """True while her window is open (whoever opened it): the event exists. Cheap: one kernel call."""
    if os.name != 'nt':
        return False
    k32 = _kernel32()
    handle = k32.OpenEventW(SYNCHRONIZE, False, name or event_name())
    if handle:
        k32.CloseHandle(handle)
        return True
    return ctypes.get_last_error() == ERROR_ACCESS_DENIED     # it is there, held by a process started as administrator


# ── open, close, install (blocking: call them from a worker thread) ─────────────────────────────────────────────
def _lines(path, start) -> list:
    """The non-empty lines a log gained after byte `start`."""
    try:
        with open(path, 'rb') as handle:
            handle.seek(start)
            text = handle.read().decode('utf-8', 'replace')
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip()]


def _said(path, start, limit=400) -> str:
    """What her window printed, as one line for the page: the last line of a traceback, else all of it."""
    lines = _lines(path, start)
    if not lines:
        return ''
    if any(line.startswith('Traceback (most recent call last)') for line in lines):
        return lines[-1][:limit]
    return ' '.join(lines)[:limit]


def _kill_tree(pid) -> None:
    """The process with its children (her window's WebView2 processes)."""
    try:
        subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], stdin=subprocess.DEVNULL, capture_output=True,
                       timeout=20, creationflags=NO_WINDOW)
    except (OSError, subprocess.SubprocessError):
        pass


def _failed(reason, code='failed') -> dict:
    return {'ok': False, 'code': code, 'reason': reason}


def start(base_url, *, power=False, mic=False, python=None, script=PET, name=None, wait=25.0, log=LOG) -> dict:
    """Open her window (pet.py --url base_url) and wait until her page is alive in it.

    power, mic: what the page that sends her there had on; her window's page takes both over once (pet.py
    PetApi.handover: no click is needed there, and nothing travels in the address).
    Returns {'ok': True} ('already': True when her window was open before), or {'ok': False, 'code', 'reason'} with
    code 'unsupported' (not Windows), 'no_python', 'not_installed' (pywebview is missing: install() adds it),
    'closed' (it opened and went away) or 'failed'."""
    global _child
    if os.name != 'nt':
        return _failed('Her desktop window is Windows-only for now.', 'unsupported')
    name = name or event_name()
    if running(name):
        return {'ok': True, 'already': True}
    python = Path(python or pet_python())
    if not python.is_file():
        return _failed(f'The Python for her desktop window was not found: {python}', 'no_python')
    if not has_pywebview(python):
        return _failed('Her desktop window needs one small install first (pywebview).', 'not_installed')
    command = [str(python), '-X', 'utf8', str(script), '--url', str(base_url), '--close-with', str(os.getpid())]
    command += ['--power'] if power else []
    command += ['--mic'] if mic else []
    log = Path(log)
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'ab') as handle:
            handle.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} the Use page's Desktop pet button: "
                         f"{' '.join(command)}\n".encode('utf-8'))
            handle.flush()
            offset = handle.tell()
            proc = subprocess.Popen(command, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=handle,
                                    stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    except OSError as error:
        return _failed(f'Her desktop window could not start: {error}')
    deadline = time.monotonic() + wait
    while True:
        if running(name + READY):
            break
        code = proc.poll()
        if code is not None:
            if running(name):                    # another start won the race: that window is hers too
                return {'ok': True, 'already': True}
            if code == 2:
                forget_pywebview(python)         # pet.py: no pywebview, or no WebView2 runtime
            said = _said(log, offset)
            if code == 0:
                return _failed(said or 'Her desktop window opened and closed again.', 'closed')
            return _failed(said or f'Her desktop window stopped with code {code}. See logs/{log.name}.')
        if time.monotonic() >= deadline:
            if running(name):                    # the window is there and her page is slow: it is hers to finish
                break
            _kill_tree(proc.pid)
            return _failed(f'Her desktop window did not open in time. See logs/{log.name}.')
        time.sleep(0.1)
    with _lock:
        _child = proc
    return {'ok': True}


def close(name=None, wait=6.0) -> dict:
    """Ask her window to close (whoever opened it) and wait until it has gone.
    {'ok': True, 'was_running': bool}, or {'ok': False, 'reason': ...} when it stays."""
    global _child
    if os.name != 'nt':
        return {'ok': True, 'was_running': False}
    name = name or event_name()
    k32 = _kernel32()
    handle = k32.OpenEventW(EVENT_MODIFY_STATE | SYNCHRONIZE, False, name)
    if not handle:
        if ctypes.get_last_error() == ERROR_FILE_NOT_FOUND:
            with _lock:
                _child = None
            return {'ok': True, 'was_running': False}
        return {'ok': False, 'reason': 'Her window was started as administrator, so this page may not close it. '
                                       'Close it with its own ✕ button (hover her).'}
    try:
        k32.SetEvent(handle)
    finally:
        k32.CloseHandle(handle)                  # an open handle would keep the event (and "running") alive
    with _lock:
        proc = _child
    deadline = time.monotonic() + wait
    while running(name) and time.monotonic() < deadline:
        time.sleep(0.1)
    if running(name) and proc is not None and proc.poll() is None:
        _kill_tree(proc.pid)                     # ours, and it did not listen
        deadline = time.monotonic() + 3.0
        while running(name) and time.monotonic() < deadline:
            time.sleep(0.1)
    if running(name):
        return {'ok': False, 'reason': 'Her window did not close. Close it with its own ✕ button (hover her).'}
    with _lock:
        _child = None
    return {'ok': True, 'was_running': True}


def install(python=None, requirements=REQUIREMENTS, log=INSTALL_LOG, timeout=600.0) -> dict:
    """pip-install her window's one package (pywebview, about 5 MB) into the Python her window runs in: the page's
    "Install and open". The same as the README's `python -m pip install -r brain/requirements-pet.txt`."""
    if os.name != 'nt':
        return _failed('Her desktop window is Windows-only for now.', 'unsupported')
    python = Path(python or pet_python())
    if not python.is_file():
        return _failed(f'The Python for her desktop window was not found: {python}', 'no_python')
    if has_pywebview(python, fresh=True):
        return {'ok': True, 'already': True}
    command = [str(python), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
               '-r', str(requirements)]
    log = Path(log)
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'wb') as handle:
            handle.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} {' '.join(command)}\n".encode('utf-8'))
            handle.flush()
            offset = handle.tell()
            code = subprocess.run(command, cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=handle,
                                  stderr=subprocess.STDOUT, timeout=timeout, creationflags=NO_WINDOW).returncode
    except subprocess.TimeoutExpired:
        return _failed(f'The install took too long and was stopped. See logs/{log.name}.', 'install_failed')
    except OSError as error:
        return _failed(f'The install could not start: {error}', 'install_failed')
    if code == 0:
        if has_pywebview(python, fresh=True):
            return {'ok': True}
        return _failed(f'pip finished, but that Python still cannot load pywebview. See logs/{log.name}.',
                       'install_failed')
    lines = _lines(log, offset)
    errors = [line for line in lines if line.startswith('ERROR:')]
    said = (errors[-1] if errors else lines[-1] if lines else f'pip stopped with code {code}.')[:300]
    return _failed(f'{said} The full output is in logs/{log.name}.', 'install_failed')
