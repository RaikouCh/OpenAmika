"""Local-only model-selection and non-destructive usage-display controls.

A display reset also asks the settlement worker (g['F_SETTLER'], f_settle.py) for a
key-usage baseline snapshot; see reports/settle.md.

/api/build_f/preset (2026-10-09) applies one validated preset to all four roles: by
name, or {"provider": "openrouter"|"alibaba"} for the provider switch (the first
available preset of that provider). Same origin/action-header rules and busy refusals
as model selection; it never accepts models, URLs or prices.

Unlock (2026-11-09, item 32): a model switch refused as busy answers 409 with code "model_busy" and what runs. The
page offers Unlock (/api/build_f/unlock): the requests no running work will finish are retired, memory jobs whose
worker ended without an outcome are recovered, and she stops what she is doing (turns, reflections, model streams).
Then it sends the same switch with "force": true, which work still in flight no longer refuses: it keeps the model it
started with, new calls take the new one.

/api/build_f/conversation: "silence_remarks" (off | rare | normal), how often she remarks on a silence ("you're
quiet"), stored in config/build_f.json and applied at once (webui's idle check reads g['SILENCE_REMARKS']).
"""
import contextlib
import functools
import json
import os
from pathlib import Path
import tempfile
import time

from f_usage import DisplayResetBusy

SILENCE_REMARKS = ('off', 'rare', 'normal')
SILENCE_FACTORS = {'normal': 1, 'rare': 3}      # rare: three times the interval (webui.IDLE_TRIGGER_SECONDS)
UNLOCK_SETTLE_S = 3.0                           # how long Unlock lets the turns it stopped wind down
MODEL_BUSY = 'Model selection is busy or unavailable. Wait for all speech and memory work to finish.'


def silence_remarks_value(value):
    """build_f.json "silence_remarks" as the brain uses it: off, rare or normal (the default, also for anything else)."""
    value = str(value or '').strip().lower()
    return value if value in SILENCE_REMARKS else 'normal'


def _write_json(path, value):
    """Atomic, in the layout the identity writer uses (indent 2, UTF-8, LF)."""
    text = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='', dir=path.parent, delete=False,
                                     prefix=path.name + '.', suffix='.tmp') as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        name = handle.name
    os.replace(name, path)


def install_controls(g, meter):
    # Native handlers read both defaults before _ws_active registration. Share
    # the role manager lock around that whole short dispatch, preventing an old
    # surface/new deep pair when a local control POST arrives simultaneously.
    manager = g.get('F_ROLES')
    if manager is not None:
        for event, name in (('message', 'ws_message'), ('inject', 'ws_inject')):
            original = g.get(name)
            if original is None:
                continue
            @functools.wraps(original)
            def dispatch(*args, _original=original, **kwargs):
                with manager.lock:
                    return _original(*args, **kwargs)
            g[name] = dispatch
            g['socketio'].on_event(event, dispatch)

    def action_request(action):
        request = g['request']
        if request.headers.get('Origin') or request.headers.get('X-Build-F-Action') != action:
            raise PermissionError('Use the OpenAmika page for this action.')
        value = request.get_json(silent=True) if request.is_json else None
        if not isinstance(value, dict):
            raise ValueError('A JSON object is required.')
        return value

    def force_flag(value):
        force = value.pop('force', False)
        if not isinstance(force, bool):
            raise ValueError('force must be true or false.')
        return force

    def model_busy(error):
        """409 for a refused switch: what runs (ModelSelectionBusy.reasons) and the code the page offers Unlock on."""
        reasons = list(getattr(error, 'reasons', None) or [])
        message = ('Model selection is busy: ' + '; '.join(reasons) + '. Wait a moment, or press Unlock '
                   '(she stops what she is doing).') if reasons else MODEL_BUSY
        return g['jsonify']({'ok': False, 'error': message, 'code': 'model_busy', 'busy': reasons}), 409

    def retire_dead():
        retire = getattr(meter, 'retire_dead', None)
        if callable(retire):
            with contextlib.suppress(Exception):
                return retire()
        return []

    @g['app'].route('/api/build_f/meter/reset', methods=['POST'])
    def reset_meter():
        try:
            value = action_request('reset-meter')
            if value != {'action': 'reset_display'}:
                raise ValueError('Invalid meter reset request.')
            # A request no running work will finish (an earlier process's, a gone thread's) is not in flight.
            retire_dead()
            with g['_ws_active_lock']:
                if g['_ws_active'] or g.get('_thinking_inflight', 0):
                    raise DisplayResetBusy('Wait for the current response to finish.')
                # Queued enrichment can be between billable calls. Do not cut
                # one response's accounting period in that gap, or call status
                # while query-cache files or memory journals are being written.
                memory = g.get('F_MEMORY')
                with contextlib.ExitStack() as locks:
                    if memory is not None:
                        for name in ('_query_lock', '_worker_lock', '_lock'):
                            lock = getattr(memory, name)
                            if not lock.acquire(blocking=False):
                                raise DisplayResetBusy('Wait for memory work to finish.')
                            locks.callback(lock.release)
                        if memory._active_retrievals or memory.status().get('pending'):
                            raise DisplayResetBusy('Wait for queued memory work to finish.')
                    boundary = meter.reset_display()
            # Cost settlement: baseline snapshot of this OpenRouter key's usage for
            # the new display period. Queued for the settlement worker; never waits
            # on the network here, and a missing/stopped worker changes nothing.
            settler = g.get('F_SETTLER')
            if settler is not None:
                with contextlib.suppress(Exception):
                    settler.on_reset(boundary)
            return g['jsonify']({'ok': True, 'display_window': boundary, 'usage': meter.summary()})
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except DisplayResetBusy:
            return g['jsonify']({'ok': False, 'error': 'Amika is busy. Wait for active requests to finish.'}), 409
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400

    @g['app'].route('/api/build_f/models', methods=['GET', 'POST'])
    def models():
        manager = g.get('F_ROLES')
        if manager is None:
            return g['jsonify']({'ok': False, 'error': 'Tested model choices are not installed yet.'}), 503
        try:
            if g['request'].method == 'POST':
                value = action_request('select-models')
                force = force_flag(value)
                if set(value) != {'selections'} or not isinstance(value['selections'], dict):
                    raise ValueError('Choose the model for each role.')
                # (a manager without force, as in older callers' fakes, gets the plain call)
                result = manager.set(value['selections'], force=True) if force else manager.set(value['selections'])
            else:
                result = manager.get()
            return g['jsonify'](result)
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400
        except RuntimeError as error:
            return model_busy(error)

    @g['app'].route('/api/build_f/preset', methods=['GET', 'POST'])
    def preset():
        manager = g.get('F_ROLES')
        if manager is None:
            return g['jsonify']({'ok': False, 'error': 'Tested model choices are not installed yet.'}), 503
        try:
            if g['request'].method == 'POST':
                value = action_request('apply-preset')
                force = force_flag(value)
                if len(value) != 1 or not set(value) <= {'preset', 'provider'}:
                    raise ValueError('Send either a preset name or a provider.')
                if 'preset' in value:
                    result = manager.apply_preset(name=value['preset'], **({'force': True} if force else {}))
                else:
                    result = manager.apply_preset(provider=value['provider'], **({'force': True} if force else {}))
            else:
                result = manager.get()
            return g['jsonify'](result)
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400
        except RuntimeError as error:
            return model_busy(error)

    @g['app'].route('/api/build_f/unlock', methods=['POST'])
    def unlock():
        """Clear what keeps the model switch (or a wipe) refusing: retire the ledger rows no running work will finish,
        recover memory jobs whose worker ended without an outcome and, with stop (the default), stop what she is
        doing. Reports what still runs. Never touches her memory, her settings or a model choice."""
        try:
            value = action_request('unlock')
            if not set(value) <= {'stop'}:
                raise ValueError('Only "stop" is accepted.')
            stop = value.get('stop', True)
            if not isinstance(stop, bool):
                raise ValueError('stop must be true or false.')
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400
        retired = len(retire_dead())
        recovered = 0
        memory = g.get('F_MEMORY')
        if memory is not None and callable(getattr(memory, 'recover_orphans', None)):
            with contextlib.suppress(Exception):
                recovered = memory.recover_orphans()
        stopped = None
        if stop and callable(g.get('F_STOP_WORK')):
            with contextlib.suppress(Exception):
                stopped = g['F_STOP_WORK']('interrupt')
            deadline = time.monotonic() + UNLOCK_SETTLE_S
            while time.monotonic() < deadline and (g.get('_ws_active') or g.get('_thinking_inflight', 0)):
                time.sleep(0.1)
            retired += len(retire_dead())
        still = []
        if callable(g.get('F_BUSY_REASONS')):
            with contextlib.suppress(Exception):
                still = g['F_BUSY_REASONS']()
        return g['jsonify']({'ok': True, 'retired_requests': retired, 'recovered_jobs': recovered,
                             'stopped': stopped, 'still_running': still})

    def conversation_settings():
        choice = silence_remarks_value(g.get('SILENCE_REMARKS'))
        base = g.get('IDLE_TRIGGER_SECONDS', 30)
        factor = SILENCE_FACTORS.get(choice)
        return {'ok': True, 'silence_remarks': choice, 'choices': list(SILENCE_REMARKS),
                'interval_s': None if factor is None else int(base * factor)}

    @g['app'].route('/api/build_f/conversation', methods=['GET', 'POST'])
    def conversation():
        try:
            if g['request'].method == 'POST':
                value = action_request('conversation')
                if set(value) != {'silence_remarks'} or value['silence_remarks'] not in SILENCE_REMARKS:
                    raise ValueError('silence_remarks must be off, rare or normal.')
                path = Path(g['__file__']).resolve().parents[1] / 'config' / 'build_f.json'
                document = json.loads(path.read_text(encoding='utf-8-sig'))
                document['silence_remarks'] = value['silence_remarks']
                _write_json(path, document)
                g['SILENCE_REMARKS'] = value['silence_remarks']
            return g['jsonify'](conversation_settings())
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400
        except OSError as error:
            return g['jsonify']({'ok': False, 'error': f'Could not write config/build_f.json: {error}'}), 503

    @g['app'].route('/api/build_f/memory/requeue', methods=['POST'])
    def requeue_memory():
        # Re-dispatch memory jobs the provider rejected outright (HTTP 4xx before any paid
        # work, e.g. a price-ceiling 404). Uncertain blocks need {"force": true}.
        memory = g.get('F_MEMORY')
        if memory is None:
            return g['jsonify']({'ok': False, 'error': 'Memory runtime is not installed.'}), 503
        try:
            value = action_request('requeue-memory')
            if not set(value) <= {'force', 'max_jobs'}:
                raise ValueError('Only force and max_jobs are accepted.')
            force = value.get('force', False)
            if not isinstance(force, bool):
                raise ValueError('force must be true or false.')
            max_jobs = value.get('max_jobs')
            if max_jobs is not None and (isinstance(max_jobs, bool) or not isinstance(max_jobs, int) or max_jobs < 0):
                raise ValueError('max_jobs must be a non-negative integer.')
            result = memory.requeue_blocked(force=force, max_jobs=max_jobs)
        except PermissionError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 403
        except ValueError as error:
            return g['jsonify']({'ok': False, 'error': str(error)}), 400
        except Exception:
            return g['jsonify']({'ok': False, 'error': 'Memory is busy or unavailable. Try after the current turn finishes.'}), 409
        flush = g.get('f_memory_flush')
        started = bool(result['count'] and flush is not None)
        if started:
            flush()
        return g['jsonify']({'ok': True, 'flush_started': started, **result, 'memory': memory.status()})

    install_catalog_check(g)


# ── is every OpenRouter model she uses still offered? ────────────────────────────────────────────────────────────
# A model chosen on Setup → Brain can leave OpenRouter's catalog (one person had picked a qwen3-235b entry that was
# gone): every reply then fails. The brain asks OpenRouter's public model list once at start (after the boot-time
# resume, never at import) and again at most every 30 minutes when a page asks; the health light and Setup → Brain
# offer "Switch back to the OpenRouter preset" (POST /api/build_f/preset {"provider": "openrouter"}).
CATALOG_MAX_AGE_S = 1800


def openrouter_models(manager, selections):
    """{role: (model_id, canonical_slug)} of the roles that run on OpenRouter in these selections."""
    out = {}
    for role, key in (selections or {}).items():
        row = (manager.options.get(role) or {}).get(key)
        if row and row.get('transport') == 'openrouter' and isinstance(row.get('config'), dict):
            config = row['config']
            out[role] = (config.get('model_id'), config.get('canonical_slug'))
    return out


def missing_models(models, offered):
    """[{role, model}] of the models (from openrouter_models) that the offered ids no longer list."""
    return [{'role': role, 'model': model} for role, (model, slug) in sorted(models.items())
            if model not in offered and (not slug or slug not in offered)]


def openrouter_preset(manager):
    """The preset "Switch back to the OpenRouter preset" applies: the first available one of that provider."""
    return next((p for p in manager.document.get('presets', [])
                 if isinstance(p, dict) and p.get('provider') == 'openrouter' and manager._preset_ok(p)), None)


def install_catalog_check(g):
    import threading
    import time
    from datetime import datetime, timezone

    state = {'at': 0.0, 'ids': None, 'error': None, 'checked_at': None}
    lock = threading.Lock()

    def status(refresh=False):
        manager = g.get('F_ROLES')
        if manager is None:
            return {'ok': False, 'error': 'Tested model choices are not installed yet.'}
        in_use = openrouter_models(manager, manager.selections)
        preset = openrouter_preset(manager)
        if not in_use and not refresh:
            return {'ok': True, 'checked': False, 'missing': [], 'preset': (preset or {}).get('name'),
                    'preset_missing': [], 'error': None, 'note': 'no role runs on OpenRouter'}
        with lock:
            if refresh or state['ids'] is None or time.monotonic() - state['at'] > CATALOG_MAX_AGE_S:
                from f_openrouter import fetch_model_ids
                try:
                    state['ids'], state['error'] = fetch_model_ids(g['http_requests']), None
                    state['checked_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
                except Exception as error:  # noqa: BLE001  (offline: say so, never guess)
                    state['error'] = f'the OpenRouter model list is unavailable right now ({type(error).__name__})'
                state['at'] = time.monotonic()
            offered = state['ids']
        if offered is None:
            return {'ok': True, 'checked': False, 'missing': [], 'preset': (preset or {}).get('name'),
                    'preset_missing': [], 'error': state['error']}
        preset_models = openrouter_models(manager, (preset or {}).get('selections') or {})
        return {'ok': True, 'checked': True, 'checked_at': state['checked_at'],
                'missing': missing_models(in_use, offered), 'preset': (preset or {}).get('name'),
                'preset_missing': missing_models(preset_models, offered), 'error': state['error']}

    g['F_CATALOG_STATUS'] = status

    @g['app'].route('/api/build_f/openrouter/catalog', methods=['GET'])
    def openrouter_catalog():
        return g['jsonify'](status(refresh=g['request'].args.get('refresh') == '1'))

    def check_at_start():
        time.sleep(3)
        try:
            result = status()
        except Exception as error:  # noqa: BLE001
            print(f'[models] could not check the OpenRouter model list: {type(error).__name__}: {error}')
            return
        for gone in result.get('missing') or []:
            print(f"[models] OpenRouter no longer offers {gone['model']} (the {gone['role']} role): every "
                  "reply that needs it fails. Setup → Brain → Switch back to the OpenRouter preset")

    previous = g.get('f_resume_pending')
    if callable(previous):
        def resume_then_check():
            previous()
            threading.Thread(target=check_at_start, daemon=True, name='F-openrouter-catalog').start()
        g['f_resume_pending'] = resume_then_check
