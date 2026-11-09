"""Confirmed active-memory reset for the isolated Build F: idle-only by default, forced on request.

No provider calls. Recovery copies are local; this is not secure deletion.

Busy, truthfully (2026-11-09, item 49 — "users trying to wipe hit a 'she is busy' error"): the wipe refused with 409
whenever the usage ledger still held a request marked 'started', and nothing retired the rows a crashed or restarted
brain had left until 15 minutes had passed. The check now retires those first (UsageMeter.retire_dead: every row an
earlier process left, any row whose thread is gone) and names what really runs. The page's first attempt waits up to
`wait_s` for her to finish (one short wait); after that it offers the forced wipe: she stops what she is doing (turns
and reflections cancelled, model streams closed), every open ledger row is retired, and the memory store fences off a
memory write or search still waiting on its model, so nothing from before reaches the empty store. The backup is
taken either way.
"""
import contextlib
from datetime import datetime, timezone
import functools
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import uuid

# The first attempt waits at most this long for her to finish (the page asks for one short wait). A forced wipe gives
# the turns it cancelled this long to wind down, then waits this long for a snapshot or a memory search in progress.
MAX_WAIT_S = 20.0
FORCE_SETTLE_S = 5.0
FORCE_LOCK_S = 15.0
POLL_S = 0.25
_PHASE_WORDS = {'surface': 'her first reply', 'deep': 'her answer', 'reflection': 'a reflection',
                'memory_write': 'the memory writer', 'query_embedding': 'a memory search',
                'memory_embedding': 'the memory writer', 'conversation': 'her answer'}


def _atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.flush(); os.fsync(handle.fileno())
        name=handle.name
    os.replace(name, path)


def _age(started_at):
    try:
        moment=datetime.fromisoformat(str(started_at).replace('Z','+00:00'))
        if moment.tzinfo is None:moment=moment.replace(tzinfo=timezone.utc)
        return max(0,int((datetime.now(timezone.utc)-moment).total_seconds()))
    except (TypeError,ValueError):
        return None


def describe_request(row):
    """One in-flight ledger row for a busy message: 'her answer (qwen3:14b, 42 s)'."""
    phase=str(row.get('phase') or '')
    what=_PHASE_WORDS.get(phase) or ('a helper ('+phase[6:]+')' if phase.startswith('agent:') else 'a model call')
    age=_age(row.get('started_at'))
    detail=', '.join(x for x in (str(row.get('model') or ''),f'{age} s' if age is not None else '') if x)
    return what+(f' ({detail})' if detail else '')


def install_reset(g, memory, meter, worker_lock, work_requested):
    brain=Path(g['__file__']).resolve().parent
    root=brain.parent
    storage=(root/'memory_f').resolve()
    profile=memory.folder.name
    if profile not in ('live','validation'):raise ValueError('Unexpected memory profile')
    pending=storage/('reset_pending_'+profile+'.json')
    gate=threading.RLock()
    activity={'count':0,'failed':False}
    # Counted up by every wipe: a reflection begun before one brings nothing back (f_bridge stale_reflection).
    epoch=g.setdefault('F_WORK_EPOCH',[0])
    paths={}
    for key,name in (('MEMORY_FILE','conversations.json'),('CONSOLIDATED_FILE','consolidated.json'),('THINKING_LOG_FILE','thinking_log.json')):
        path=Path(g.get(key,Path('memories')/name))
        if not path.is_absolute():path=brain/path
        path=path.resolve()
        if path != (brain/'memories'/name).resolve():raise ValueError('Unexpected context path')
        paths[name]=path

    def clear_context():
        for name,path in paths.items():_atomic(path,{'turns':[]} if name=='conversations.json' else {'entries':[]} if name=='thinking_log.json' else {'memories':[]})
        for key in ('CONVERSATION_HISTORY','CONSOLIDATED_MEMORIES','THINKING_LOG','_COMPLETED_CPS'):
            if key in g:g[key].clear()
        g['_pending_think']=None
        g['_pending_seq']=g.get('_pending_seq',0)+1
        g['_CURRENT_TURN_NUM']=0
        if '_init_current_cp' in g:g['_init_current_cp']()

    def finish_transaction(transaction,force=False):
        backup=(storage/'backups'/transaction['backup_id']).resolve()
        if backup.parent != (storage/'backups').resolve():raise ValueError('Invalid backup path')
        # A runtime wipe has its own recovery journal. It can complete during
        # MemoryRuntime startup before this cross-store journal resumes.
        marker=memory.folder/'reset.json'
        reset=json.loads(marker.read_text(encoding='utf-8')) if marker.exists() else {}
        already=(str(backup)==reset.get('backup_dir') and reset.get('phase')=='complete')
        if transaction.get('phase')!='memory_cleared' and not already:
            if force:memory.wipe(backup,timeout=FORCE_LOCK_S,force=True)
            else:memory.wipe(backup)
        epoch[0]+=1
        transaction['phase']='memory_cleared';_atomic(pending,transaction)
        clear_context()
        work_requested.clear()
        transaction['phase']='complete'
        _atomic(backup/'reset_receipt.json',transaction)
        # Remove only this exact transaction marker; all evidence is backed up.
        pending.unlink()
        return backup

    if pending.exists():
        # Main has not loaded recent-context files yet. Finish a confirmed reset
        # before an old prompt or historical seed can become active again.
        finish_transaction(json.loads(pending.read_text(encoding='utf-8')))

    @contextlib.contextmanager
    def operation():
        with gate:
            if activity['failed']:raise RuntimeError('Memory reset needs recovery; restart Build F.')
            activity['count']+=1
        try:yield
        finally:
            with gate:activity['count']-=1

    for name in ('_ws_run_generation','run_thinking_once'):
        original=g[name]
        @functools.wraps(original)
        def wrapped(*args,_original=original,**kwargs):
            with operation():return _original(*args,**kwargs)
        g[name]=wrapped
    for name in ('_start_message_gen','_start_inject_gen','trigger_thinking_async'):
        if name not in g:continue
        original=g[name]
        @functools.wraps(original)
        def dispatch(*args,_original=original,**kwargs):
            with gate:
                if activity['failed']:raise RuntimeError('Memory reset needs recovery; restart Build F.')
                return _original(*args,**kwargs)
        g[name]=dispatch

    def in_flight():
        """The ledger's open requests, after retiring the ones that can never finish (an earlier process's, a gone
        thread's) and, as before, any older than STALE_AFTER_S."""
        for name in ('retire_dead','sweep_stale'):
            sweep=getattr(meter,name,None)
            if callable(sweep):
                with contextlib.suppress(Exception):sweep()
        rows=getattr(meter,'active_requests',None)
        if callable(rows):return rows()
        return [{}]*int(meter.summary()['active_requests'])

    def busy_reasons():
        """What really runs, in words for the page; [] when she is idle."""
        reasons=[]
        with g['_ws_active_lock']:
            if g['_ws_active']:reasons.append('she is answering')
        if g.get('_thinking_inflight',0):reasons.append('she is reflecting')
        with gate:
            if activity['count'] and not reasons:reasons.append('a turn is finishing')
        rows=in_flight()
        if rows:reasons.append('model call(s) in flight: '+', '.join(describe_request(row) for row in rows[:3])
                               +(f' and {len(rows)-3} more' if len(rows)>3 else ''))
        if worker_lock.locked() or memory._worker_lock.locked():
            reasons.append('her memory writer is saving the last conversation')
        if memory._query_lock.locked() or memory._active_retrievals:reasons.append('a memory search is running')
        return reasons

    def busy(reasons):
        return {'ok':False,'code':'busy','busy':reasons,
                'error':'Amika is busy: '+'; '.join(reasons)+'. Wait a few seconds and try again, or force it '
                        '(she stops what she is doing).'},409

    def idle():
        with g['_ws_active_lock']:
            if g['_ws_active']:return False
        with gate:
            return not activity['count'] and not g.get('_thinking_inflight',0)

    def attempt(force):
        from f_memory import MemoryBusyError
        with gate:
            if activity['failed']:return {'ok':False,'error':'Memory reset needs recovery; restart Build F.'},503
            retired=[]
            if force:
                # She was stopped already (reset_memory); what still runs is fenced off, not waited for.
                with contextlib.suppress(Exception):retired=meter.retire_all()
                got=worker_lock.acquire(timeout=2.0)
            else:
                reasons=busy_reasons()
                if reasons:return busy(reasons)
                got=worker_lock.acquire(blocking=False)
                if not got:return busy(['her memory writer is saving the last conversation'])
            backup=None
            try:
                with g['_hist_lock'], g.get('_think_lock',contextlib.nullcontext()):
                    backup_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:12]
                    backup=storage/'backups'/backup_id
                    (backup/'brain_context').mkdir(parents=True,exist_ok=False)
                    for name,path in paths.items():
                        if path.exists():shutil.copy2(path,backup/'brain_context'/name)
                    transaction={'profile':profile,'backup_id':backup_id,'phase':'prepared','confirmed_at':datetime.now(timezone.utc).isoformat(),
                                 'forced':bool(force)}
                    _atomic(pending,transaction)
                    finish_transaction(transaction,force=force)
                    result={'ok':True,'backup_id':backup_id,'memory':memory.status(),'usage':meter.summary()}
                    if force:result.update(forced=True,retired_requests=len(retired))
                    return result,200
            except MemoryBusyError:
                # No runtime data changed if its concurrency gate refused reset: drop this attempt's marker and its
                # half-made backup folder (only the context copies are in it), so a retry starts clean.
                if pending.exists():pending.unlink()
                if backup is not None:shutil.rmtree(backup,ignore_errors=True)
                return busy(['a memory search or snapshot is still being written'])
            except Exception:
                activity['failed']=True
                return {'ok':False,'error':'Reset could not finish. Your recovery backup is retained; restart Build F to recover.'},503
            finally:
                if got:worker_lock.release()

    def reset_memory(force=False,wait_s=0.0):
        """Wipe her memory (backup kept). Waits up to wait_s (at most MAX_WAIT_S) for her to finish; force: she stops
        what she is doing first and nothing still running can refuse it."""
        try:
            budget=max(0.0,min(float(wait_s or 0.0),MAX_WAIT_S))
        except (TypeError,ValueError):
            budget=0.0
        deadline=time.monotonic()+budget
        stopped=None
        if force:
            stop=g.get('F_STOP_WORK')
            if callable(stop):
                with contextlib.suppress(Exception):stopped=stop('discard')
            settle=time.monotonic()+FORCE_SETTLE_S
            while not idle() and time.monotonic()<settle:time.sleep(POLL_S)
        while True:
            result,code=attempt(force)
            if code!=409 or time.monotonic()>=deadline:
                if code==200 and stopped is not None:result['stopped']=stopped
                return result,code
            time.sleep(POLL_S)

    def request_options(data):
        """force (true/false) and wait_s (0-20 s) from a wipe or reset request; ValueError when malformed."""
        force=data.get('force',False)
        if not isinstance(force,bool):raise ValueError('force must be true or false.')
        wait_s=data.get('wait_s',0)
        if isinstance(wait_s,bool) or not isinstance(wait_s,(int,float)) or not 0<=wait_s<=MAX_WAIT_S:
            raise ValueError(f'wait_s must be a number of seconds from 0 to {int(MAX_WAIT_S)}.')
        return force,float(wait_s)

    @g['app'].route('/api/build_f/wipe',methods=['POST'])
    def wipe_route():
        request=g['request']
        if request.headers.get('Origin'):
            return g['jsonify']({'ok':False,'error':'Use the OpenAmika page to confirm this action.'}),403
        if request.headers.get('X-Build-F-Action')!='wipe-memory':
            return g['jsonify']({'ok':False,'error':'Explicit wipe action required.'}),403
        data=request.get_json(silent=True) if request.is_json else None
        if not isinstance(data,dict) or data.get('confirmation')!='WIPE':
            return g['jsonify']({'ok':False,'error':'Type WIPE to confirm.'}),400
        try:
            force,wait_s=request_options(data)
        except ValueError as error:
            return g['jsonify']({'ok':False,'error':str(error)}),400
        result,code=reset_memory(force=force,wait_s=wait_s)
        return g['jsonify'](result),code

    if 'clear_memory' in g['app'].view_functions:
        g['app'].view_functions['clear_memory']=lambda:(g['jsonify']({'ok':False,'error':'Use the confirmed Build F wipe control.'}),409)
    g['F_RESET_MEMORY']=reset_memory
    g['F_RESET_OPTIONS']=request_options
    g['F_BUSY_REASONS']=busy_reasons


CONTEXT_FILES=('conversations.json','consolidated.json','thinking_log.json')


def wipe_offline(root,profile=None):
    """Wipe her memory while no brain runs (`python launch.py --wipe-memory`): the Setup page's wipe, same files.
    The backup first (memory_f/backups/<id>: the evidence store and brain/memories/), then the empty store and
    transcript; the ledger's open requests are retired (no brain runs, so none of them can finish). Nothing is sent
    anywhere. A crash midway is finished by the brain's next start (memory_f/reset_pending_<profile>.json, the same
    journal as a live wipe). Returns {backup_id, backup_dir, retired_requests}."""
    from f_memory import MemoryRuntime
    root=Path(root).resolve()
    storage=(root/'memory_f').resolve()
    if profile is None:
        try:cfg=json.loads((root/'config'/'build_f.json').read_text(encoding='utf-8-sig'))
        except (OSError,ValueError):cfg={}
        profile=cfg.get('memory_profile','live') if isinstance(cfg,dict) else 'live'
    if profile not in ('live','validation'):raise ValueError('Unexpected memory profile')
    pending=storage/('reset_pending_'+profile+'.json')
    if pending.exists():
        raise RuntimeError(f'an earlier wipe is unfinished ({pending.name}): start OpenAmika once (it finishes it), '
                           'then run this again if you still need to')
    storage.mkdir(parents=True,exist_ok=True)
    paths={name:root/'brain'/'memories'/name for name in CONTEXT_FILES}
    memory=MemoryRuntime(storage/profile,seed_path=root/'config'/'seed.json')
    try:
        backup_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:12]
        backup=storage/'backups'/backup_id
        (backup/'brain_context').mkdir(parents=True,exist_ok=False)
        for name,path in paths.items():
            if path.exists():shutil.copy2(path,backup/'brain_context'/name)
        transaction={'profile':profile,'backup_id':backup_id,'phase':'prepared',
                     'confirmed_at':datetime.now(timezone.utc).isoformat(),'offline':True}
        _atomic(pending,transaction)
        memory.wipe(backup)
        transaction['phase']='memory_cleared';_atomic(pending,transaction)
        for name,path in paths.items():
            _atomic(path,{'turns':[]} if name=='conversations.json' else {'entries':[]} if name=='thinking_log.json' else {'memories':[]})
        transaction['phase']='complete'
        _atomic(backup/'reset_receipt.json',transaction)
        pending.unlink()
    finally:
        memory.close()
    retired=[]
    ledger=storage/'usage.sqlite'
    if ledger.exists():
        from f_usage import UsageMeter
        with contextlib.suppress(Exception):retired=UsageMeter(ledger).retire_dead()
    return {'backup_id':backup_id,'backup_dir':str(backup),'retired_requests':len(retired)}
