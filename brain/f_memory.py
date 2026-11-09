"""Durable, on-demand runtime for the tested Candidate F memory algorithm.

No scheduler, network client, credentials, or benchmark questions live here.
Callbacks own API dispatch, metering and extraction schema validation. A failed or
uncertain dispatch blocks its job. With ``auto_retry`` on (f_bridge passes build_f.json
``memory_auto_retry``, default on since 2026-10-10), a job whose provider dispatch
failed transiently (TRANSIENT_ERROR, or a restart cut it) waits in state "retry_wait"
instead; the caller's bounded worker (flush_pending) resumes it at its last durable
stage after a back-off, at most ``max_attempts`` times, and then it blocks as before.
The runtime itself never sleeps or dispatches on its own: the caller decides when to flush.

2026-10 scaling fixes (a companion months in production: 4,000 jobs, 12,700 vectors, 218 MB snapshot):
  A. A finished job file moves under jobs/completed (totals.json keeps its counts), so the worker and
     status() read only what is still pending; the query-cache's blocked entries are tracked in memory.
  B. The snapshot is written once per batch of jobs, after the turn in flight (persist_gate), forced
     after persist_delay_s; a job is marked complete only after the write that holds it (settle()).
  C. Document vectors live in a binary sidecar beside state.json (f_method.VectorBlob).
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import math
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from f_method import CandidateF, sidecar_files


DIMENSIONS = 768
EMBEDDING_MODEL = "gemini-embedding-2"

# Automatic bounded retry (2026-10-10, MekaHime_Live_2 "memory degraded" incidents: OpenRouter HTTP 520,
# read timeouts and a one-token writer reply). Defaults of build_f.json "memory_auto_retry" (f_bridge).
AUTO_RETRY_DEFAULTS = {"enabled": True, "max_attempts": 3, "backoff_s": [60, 300, 1200]}
RESTART_ERROR = "Process stopped during API dispatch; outcome uncertain"
# Job states in which a failure means the provider dispatch itself failed: no result of it was stored,
# so a retry repeats only that dispatch. A failure in any other state comes from re-validating or
# ingesting stored results and would fail the same way again.
DISPATCH_STATES = frozenset({"extracting", "embedding"})
# Stored "Type: message" error texts worth repeating later: HTTP 5xx and 429, timeouts and connection
# failures, a broken or unparsable provider/writer response, the bridge's native/local call failures of
# those kinds (f_bridge json_call), and a dispatch cut by a restart. Everything else (other 4xx, our own
# request/config validation, "inspect ... before retrying" accounting anomalies) blocks at once, as before.
TRANSIENT_ERROR = re.compile(
    r"^(?:HTTPError: (?:5\d\d|429) "
    r"|(?:ReadTimeout|ConnectTimeout|Timeout|TimeoutError|ConnectionError|ConnectionResetError"
    r"|ConnectionAbortedError|ConnectionRefusedError|BrokenPipeError|ChunkedEncodingError"
    r"|ContentDecodingError|ProtocolError|RemoteDisconnected|IncompleteRead|SSLError|ProxyError"
    r"|JSONDecodeError): "
    r"|ValueError: Expected object with facts array"
    r"|OpenRouterError: (?:Stream ended without its completion marker|OpenRouter returned an error event"
    r"|Model Studio returned an error event|Provider returned (?:no completion choice|no text content"
    r"|a non-object event|non-text content))"
    r"|RuntimeError: Build F provider request failed \((?:HTTPError (?:5\d\d|429)|ReadTimeout"
    r"|ConnectTimeout|Timeout|ConnectionError|ChunkedEncodingError|JSONDecodeError)\)"
    r"|" + re.escape(RESTART_ERROR) + r"$)")


def transient_failure(message, failed_state):
    """True when a job failure may succeed if its provider dispatch is repeated later."""
    return failed_state in DISPATCH_STATES and bool(TRANSIENT_ERROR.match(str(message or "")))


def auto_retry_policy(value):
    """Normalise build_f.json "memory_auto_retry". None/False: off (the runtime default; failed jobs
    block as before). True: AUTO_RETRY_DEFAULTS. An object overrides the defaults; a back-off list
    shorter than max_attempts repeats its last delay."""
    if value is None or value is False:
        value = {"enabled": False}
    elif value is True:
        value = {}
    if not isinstance(value, dict) or set(value) - set(AUTO_RETRY_DEFAULTS):
        raise ValueError("memory_auto_retry must be true, false or an object with enabled, max_attempts, backoff_s")
    policy = dict(AUTO_RETRY_DEFAULTS, **value)
    attempts, backoff = policy["max_attempts"], policy["backoff_s"]
    if not isinstance(policy["enabled"], bool):
        raise ValueError("memory_auto_retry.enabled must be true or false")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or not 0 <= attempts <= 10:
        raise ValueError("memory_auto_retry.max_attempts must be an integer from 0 to 10")
    if (not isinstance(backoff, list) or not 1 <= len(backoff) <= 10
            or any(isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s)
                   or not 1 <= s <= 86400 for s in backoff)):
        raise ValueError("memory_auto_retry.backoff_s must list 1 to 10 delays of 1 to 86400 seconds")
    return {"enabled": policy["enabled"] and attempts > 0, "max_attempts": attempts, "backoff_s": list(backoff)}


class MemoryBusyError(RuntimeError):
    """A reset was refused because retrieval or ingestion is currently active."""


class MemoryResetPendingError(RuntimeError):
    """Reset filesystem work was interrupted; restart completes it before use."""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def _epoch(value):
    """ISO time -> epoch seconds; 0.0 (due at once) when missing or unreadable."""
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return 0.0
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write(path, value):
    """Durable replacement; never leave a half-written JSON checkpoint."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # R21(a): serialise first, then one write (json.dump streams many small writes).
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                         prefix=target.name + ".", suffix=".tmp",
                                         delete=False) as handle:
            temporary = handle.name
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


# Assistant label inside embedded documents; f_bridge.install sets it from "persona_name".
PERSONA_NAME = "Amika"


def event_document(event):
    """Same document representation as the frozen F benchmark."""
    pieces = [f"Date: {event['time']}"]
    if event.get("user"):
        pieces.append("User: " + event["user"])
    if event.get("assistant"):
        pieces.append(PERSONA_NAME + ": " + event["assistant"])
    if event.get("cue"):
        pieces.append("Operator cue (not user speech): " + event["cue"])
    return "\n".join(pieces)


def record_document(record):
    return (f"Date: {record['date']}\nSource speakers: {record['source_kind']}\n"
            f"{record['text']}\nEntities: " + ", ".join(record.get("entities", [])))


def _vectors(raw, count):
    if not isinstance(raw, list) or len(raw) != count:
        raise ValueError("Embedding result count mismatch")
    output = []
    for vector in raw:
        if not isinstance(vector, list) or len(vector) != DIMENSIONS or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in vector):
            raise ValueError("Embedding must contain 768 finite numbers")
        norm = math.sqrt(sum(v * v for v in vector))
        if not norm:
            raise ValueError("Zero embedding")
        output.append([v / norm for v in vector])
    return output


def _compact_rejections(value):
    """Only validation metadata belongs in the runtime job's quarantine list."""
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("Extraction rejected metadata must be an array of objects")
    return [{"id": row.get("id") if isinstance(row.get("id"), str) else None,
             "reason": str(row.get("reason", "rejected"))[:500],
             "index": row.get("index") if isinstance(row.get("index"), int)
                      and not isinstance(row.get("index"), bool) else None}
            for row in value]


class MemoryRuntime:
    """Single-process local F store with injected, metered API callbacks.

    extract_fn(events, chunk_id) -> list[fact] or {"facts": list[fact]}.
    embed_fn(texts, task_type) -> list[list[float]], task_type=document|query.
    archive() does no API work. flush_pending() does a bounded amount only when
    explicitly called. Do not run multiple processes against the same folder.
    auto_retry: see auto_retry_policy (None = off); clock() -> epoch seconds.
    """

    def __init__(self, folder, extract_fn=None, embed_fn=None, seed_path=None,
                 budget_chars=8000, max_jobs_per_flush=4, fact_packets=6, event_candidates=8,
                 embedding_model=None, auto_retry=None, clock=None, persist_delay_s=120.0):
        self.folder = Path(folder).resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        self.jobs_dir = self.folder / "jobs"
        self.done_dir = self.jobs_dir / "completed"          # A: finished job files, out of the worker's way
        self.totals_path = self.done_dir / "totals.json"
        self.queries_dir = self.folder / "query_cache"
        self.state_path = self.folder / "state.json"
        self.reset_path = self.folder / "reset.json"
        self.extract_fn, self.embed_fn = extract_fn, embed_fn
        # The embedding model behind every document and query vector of this profile (2026-10-05:
        # configurable; "gemini-embedding-2" or the local "bge-m3-d768"). embedding.json records it.
        self.embedding_model = str(embedding_model or EMBEDDING_MODEL)
        self.marker_path = self.folder / "embedding.json"
        self.budget_chars = max(0, int(budget_chars))
        # TELEMETRY_SPEC §4: how many fact groups / original-event candidates a retrieval considers.
        self.fact_packets = max(0, int(fact_packets))
        self.event_candidates = max(0, int(event_candidates))
        # Optional job_context(event_id) -> context manager wrapped around one job's
        # extraction and embedding calls (the bridge uses it to attribute the metered
        # memory_write / memory_embedding calls to the archived turn). None = no wrapper.
        self.job_context = None
        self.max_jobs_per_flush = max(1, int(max_jobs_per_flush))
        self._lock = threading.RLock()
        self._worker_lock = threading.Lock()
        self._query_lock = threading.Lock()
        self._last_error = None
        self._last_retrieval_degraded = False
        self._closed = False
        self._reset_pending = False
        self._active_retrievals = 0
        # The wipe fence: wipe() counts up, under every lock it holds. Work that began before a wipe (a memory write
        # or a retrieval still waiting on its provider when a forced wipe went ahead without it) compares its own count
        # with this one before every write and drops what it brings back: nothing from before reaches the empty store.
        self._wipes = 0
        # Automatic bounded retry (module docstring). retry_gate() -> bool is set by the bridge: False while
        # a conversation turn or reflection is active, when no automatic retry may start. on_auto_retry() is
        # called after a retry was scheduled (the bridge wakes its timer). _retry_due: job file name -> due
        # time of every "retry_wait" job, rebuilt by each flush_pending scan.
        self.auto_retry = auto_retry_policy(auto_retry)
        self.clock = clock or time.time
        self.retry_gate = None
        self.on_auto_retry = None
        self._retry_due = {}
        self._auto_retry_dispatched = 0
        self._retry_note = None   # (job file name, _last_error text) of the last scheduled retry
        # B: persist_gate() -> bool is set by the bridge (False while a turn is in flight). _ingested: (job
        # path, job) merged into the model and waiting for the snapshot write that makes them durable; their
        # files are marked complete only after it. _dirty_since: when the first unwritten change happened.
        self.persist_gate = None
        self.persist_delay_s = max(0.0, float(persist_delay_s))
        self._dirty_since = None
        self._ingested = []
        self._totals = dict.fromkeys(self._TOTAL_KEYS, 0)
        self._query_blocked = set()
        self.startup_notes = []    # one-time housekeeping done at startup, for the operator's log
        self._last_reset = _read(self.reset_path) if self.reset_path.exists() else None
        if self._last_reset is not None:
            self._validate_reset_marker(self._last_reset)
            if self._last_reset["phase"] == "started":
                # Must run before creating job directories or loading any seed:
                # old journals must never resurrect memories after reset began.
                self._last_reset = self._finish_reset(self._last_reset)
        self.jobs_dir.mkdir(exist_ok=True)
        self.queries_dir.mkdir(exist_ok=True)
        seed = Path(seed_path) if seed_path is not None else self.folder / "seed.json"
        if self.state_path.exists():
            self.model = CandidateF.reload(self.state_path)
            if self.model.loaded_layout == "inline" and CandidateF._vector_payload(self.model.vectors)["documents"]:
                # C, once: the old all-in-one snapshot becomes JSON + vector sidecar; the original is kept.
                backup = self.state_path.with_name(f"state.json.bak_inline_{time.strftime('%Y%m%d-%H%M%S')}")
                if not backup.exists():
                    backup.write_bytes(self.state_path.read_bytes())
                self.model.persist(self.state_path)
                self.startup_notes.append(f"snapshot converted to JSON + vector sidecar ({sidecar_files(self.state_path)[-1].name}); "
                                          f"the old file is kept as {backup.name}")
        elif seed.exists() and self._last_reset is None:
            value = _read(seed)
            if value.get("method_id") == "F":
                self.model = CandidateF.reload(seed)
            else:
                self.model = CandidateF(value.get("events", []),
                                        value.get("records", {"facts": []}), value.get("vectors"))
            self.model.persist(self.state_path)
        else:
            self.model = CandidateF([], {"facts": []}, {"documents": {}, "queries": {}})
            self.model.persist(self.state_path)
        self._check_embedding_marker()
        self._totals = self._load_totals()
        self._query_blocked = self._scan_query_cache()
        self._recover_jobs()

    @staticmethod
    def _empty_model():
        return CandidateF([], {"facts": []}, {"documents": {}, "queries": {}})

    @staticmethod
    def _reject_link(path):
        # Windows junctions are reparse points too. A reset must never move or
        # inspect a directory whose resolved target escapes the intended store.
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Memory reset refuses symlink/reparse paths: " + str(path))

    def _validated_backup(self, backup_dir):
        candidate = Path(backup_dir)
        if not candidate.is_absolute():
            raise ValueError("Memory backup path must be absolute")
        prefix = self.folder.parent / "backups"
        if candidate.parent != prefix:
            raise ValueError("Memory backup must be a direct child of " + str(prefix))
        self._reject_link(prefix)
        self._reject_link(candidate)
        resolved = candidate.resolve()
        if resolved.parent != prefix.resolve() or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", resolved.name):
            raise ValueError("Memory backup must be a unique direct child of " + str(prefix))
        if resolved == self.folder or self.folder in resolved.parents:
            raise ValueError("Memory backup must be outside the active profile")
        for name in ("state.json", "jobs", "query_cache", "quarantine", "reset_manifest.json"):
            self._reject_link(resolved / name)
        for name in ("state.json", "jobs", "query_cache", "quarantine", "reset.json"):
            source = self.folder / name
            self._reject_link(source)
            if source.resolve().parent != self.folder:
                raise ValueError("Memory reset source escaped its active profile")
        return resolved

    def _check_embedding_marker(self):
        """A profile's vectors belong to one embedding model. embedding.json names it; a profile without the
        marker is a legacy Gemini profile (its vectors came from gemini-embedding-2) unless it has no
        document vectors at all. A mismatch refuses to start: run migrate_embeddings.py first."""
        marker = _read(self.marker_path) if self.marker_path.exists() else None
        if marker is None:
            documents = CandidateF._vector_payload(self.model.vectors)["documents"]
            stored = EMBEDDING_MODEL if documents else self.embedding_model
            if stored != self.embedding_model:
                raise RuntimeError(f"Memory profile {self.folder} holds {len(documents)} vectors of {stored}; configured "
                                   f"embedding model is {self.embedding_model}. Run migrate_embeddings.py before starting.")
            _write(self.marker_path, {"model": self.embedding_model, "dimensions": DIMENSIONS, "created_at": _now(),
                                      "source": "MemoryRuntime (legacy profile)" if documents else "MemoryRuntime (empty profile)"})
            return
        if marker.get("model") != self.embedding_model or int(marker.get("dimensions", DIMENSIONS)) != DIMENSIONS:
            raise RuntimeError(f"Memory profile {self.folder} holds vectors of {marker.get('model')} ({marker.get('dimensions')} dims); "
                               f"configured embedding model is {self.embedding_model} ({DIMENSIONS}). Run migrate_embeddings.py first.")

    def _validate_reset_marker(self, marker):
        if (not isinstance(marker, dict) or marker.get("version") != 1
                or marker.get("phase") not in {"started", "complete"}
                or marker.get("runtime_folder") != str(self.folder)
                or set(marker.get("existed", {})) != {"state.json", "jobs", "query_cache", "quarantine"}
                or any(not isinstance(value, bool) for value in marker["existed"].values())):
            raise ValueError("Invalid memory reset transaction marker")
        backup = self._validated_backup(marker.get("backup_dir", ""))
        if marker.get("reset_id") != backup.name:
            raise ValueError("Memory reset identity does not match backup")
        return backup

    def _finish_reset(self, marker):
        """Idempotently finish an already-authorized reset, without any APIs.

        Each rename is atomic on the same filesystem. reset.json is written
        before the first rename, so a crash at any intermediate point restarts
        into completion of this transaction, never into seed/job recovery.
        """
        backup = self._validate_reset_marker(marker)
        backup.mkdir(parents=True, exist_ok=True)
        # The embedding marker stays with the profile (the empty store keeps the configured model); the
        # backup gets a copy so it documents which model the backed-up vectors belong to.
        marker_file = self.folder / "embedding.json"
        if marker_file.exists() and not (backup / marker_file.name).exists():
            (backup / marker_file.name).write_bytes(marker_file.read_bytes())
        for name, existed in marker["existed"].items():
            source, destination = self.folder / name, backup / name
            if not existed:
                # This path was absent before reset, so it may only be a newly
                # recreated empty cache after an interrupted completion write.
                if source.exists() and (not source.is_dir() or any(source.iterdir())):
                    raise ValueError("Unexpected data appeared during reset: " + name)
                continue
            if destination.exists():
                if source.exists():
                    if name == "state.json":
                        current = CandidateF.reload(source)
                        vectors = current._vector_payload(current.vectors)
                        if current.events or current.records.get("facts") or any(vectors.values()):
                            raise ValueError("Ambiguous active state during reset recovery")
                    elif not source.is_dir() or any(source.iterdir()):
                        raise ValueError("Ambiguous active cache during reset recovery: " + name)
                continue
            if not source.exists():
                raise ValueError("Reset evidence missing from both active store and backup: " + name)
            # Both final paths have been verified under the profile/backup above.
            os.replace(source, destination)
        # The snapshot's vector sidecar(s) follow state.json into the backup (C). The empty snapshot
        # written next has none, and its persist would otherwise delete them as stale.
        for sidecar in sidecar_files(self.state_path):
            destination = backup / sidecar.name
            if destination.exists():
                sidecar.unlink()          # the same content (the name is its digest) already arrived
            else:
                os.replace(sidecar, destination)
        empty = self._empty_model()
        empty.persist(self.state_path)
        self.jobs_dir.mkdir(exist_ok=True)
        self.queries_dir.mkdir(exist_ok=True)
        (self.folder / "quarantine").mkdir(exist_ok=True)
        completed = dict(marker, phase="complete", completed_at=_now())
        _write(backup / "reset_manifest.json", completed)
        # Keep this marker permanently: an accidentally missing empty state must
        # never trigger automatic re-import of the original historical seed.
        _write(self.reset_path, completed)
        return completed

    def _require_ready(self):
        if self._reset_pending:
            raise MemoryResetPendingError("Memory reset is incomplete; restart to finish recovery before use")
        if self._closed:
            raise RuntimeError("Memory runtime is closed")

    def wipe(self, backup_dir, *, timeout=0.0, force=False):
        """Back up this profile's memory and atomically install an empty state.

        Refuses active work, after waiting up to `timeout` seconds for its locks. No calls are made to either model
        callback. If a filesystem error interrupts the operation, new work is
        blocked and the durable transaction completes during the next startup.
        The caller separately owns recent conversation/thought history and the
        usage ledger; this method touches neither.

        force (the forced wipe, "she stops what she is doing"): a memory write still waiting on its model and a
        retrieval between its steps no longer refuse the wipe. They are fenced off instead (self._wipes): whatever
        they bring back afterwards is dropped, never written into the empty store. The state lock and the query lock
        are still waited for: a snapshot or query-cache write in progress always finishes first.
        """
        deadline = time.monotonic() + max(0.0, float(timeout or 0.0))
        acquired = []
        try:
            for lock in (self._query_lock, self._worker_lock, self._lock):
                remaining = deadline - time.monotonic()
                if force and lock is self._worker_lock:
                    remaining = min(remaining, 1.0)     # a write waiting on its model is fenced off, not waited for
                if lock.acquire(timeout=remaining) if remaining > 0 else lock.acquire(blocking=False):
                    acquired.append(lock)
                elif not (force and lock is self._worker_lock):
                    raise MemoryBusyError("Memory is busy retrieving or saving; wait for the current turn to finish")
            self._require_ready()
            if self._active_retrievals and not force:
                raise MemoryBusyError("Memory retrieval is still active; wait for the current turn to finish")
            self._wipes += 1              # the fence: nothing begun before this point writes into the new store
            self.settle(force=True)       # B: what was ingested goes into the backup's snapshot, not the void
            backup = self._validated_backup(backup_dir)
            names = ("state.json", "jobs", "query_cache", "quarantine")
            if any((backup / name).exists() for name in (*names, "reset_manifest.json")):
                raise ValueError("Memory backup target already contains a reset; choose a new unique directory")
            removed = {"events": len(self.model.events), "searchable_events": len(self.model.safe_events),
                       "facts": len(self.model.records.get("facts", [])), "accepted_facts": len(self.model.facts),
                       "jobs": len(list(self.jobs_dir.glob("*.json"))) + self._totals["complete"],
                       "query_embeddings": len(list(self.queries_dir.glob("*.json"))),
                       "quarantine_files": len(list((self.folder / "quarantine").glob("*.json")))}
            marker = {"version": 1, "phase": "started", "runtime_folder": str(self.folder),
                      "backup_dir": str(backup), "reset_id": backup.name, "started_at": _now(),
                      "existed": {name: (self.folder / name).exists() for name in names}, "removed": removed}
            self._reset_pending = True
            self._last_reset = marker
            try:
                _write(self.reset_path, marker)
                completed = self._finish_reset(marker)
            except Exception:
                self._last_error = "Memory reset interrupted; restart is required to finish recovery"
                raise
            self.model = self._empty_model()
            self._totals = dict.fromkeys(self._TOTAL_KEYS, 0)
            self._query_blocked = set()
            self._ingested, self._dirty_since = [], None
            self._last_reset = completed
            self._reset_pending = False
            self._last_error = None
            self._last_retrieval_degraded = False
            self._retry_due = {}
            return {"ok": True, "reset_id": completed["reset_id"], "backup_dir": str(backup),
                    "removed": removed, "events": 0, "facts": 0, "seed_disabled": True,
                    "completed_at": completed["completed_at"]}
        finally:
            for lock in reversed(acquired):
                lock.release()

    # ───────── A: finished job files leave the live folder ─────────
    _TOTAL_KEYS = ("complete", "quarantined_facts", "attempts", "recovered")

    @staticmethod
    def _count_job(totals, job):
        record = job.get("auto_retry") or {}
        totals["complete"] += 1
        totals["quarantined_facts"] += len(job.get("quarantined") or [])
        totals["attempts"] += len(record.get("attempts") or [])
        totals["recovered"] += bool(record.get("recovered_at"))

    def _load_totals(self):
        """The counts status() reports for archived jobs; rebuilt once from the archive when missing."""
        try:
            stored = _read(self.totals_path)
            return {key: int(stored.get(key, 0)) for key in self._TOTAL_KEYS}
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        totals = dict.fromkeys(self._TOTAL_KEYS, 0)
        if self.done_dir.is_dir():
            for path in self.done_dir.glob("*.json"):
                if path.name == self.totals_path.name:
                    continue
                with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                    self._count_job(totals, _read(path))
            if totals["complete"]:
                _write(self.totals_path, totals)
        return totals

    def _archive_job(self, path, job, write_totals=True):
        """A finished job file moves under jobs/completed: the worker and status() read only what is still
        pending in jobs/. Every receipt is kept; totals.json keeps the counts status() reports (a caller
        archiving a batch writes it once at the end)."""
        self.done_dir.mkdir(exist_ok=True)
        destination = self.done_dir / path.name
        if destination.exists():
            path.unlink()
        else:
            os.replace(path, destination)
        self._count_job(self._totals, job)
        if write_totals:
            _write(self.totals_path, self._totals)

    def _scan_query_cache(self):
        """Query-cache entries that did not complete are discarded at startup: a query left 'dispatching'
        or 'received' by a process that died mid-call, or one that failed against an embedder that was still
        loading, says nothing about the embedder running now, and the next identical query simply embeds
        again. (Until 2026-11-02 such leftovers counted as blocked, so one restart that interrupted a
        retrieval left the brain reporting itself degraded for good.) Blocked entries are only ever added
        by _query_vector while this process runs, and it retries them on the next ask."""
        stale = 0
        for path in self.queries_dir.glob("*.json"):
            try:
                state = _read(path).get("state")
            except (OSError, ValueError, AttributeError):
                state = None
            if state != "complete":
                try:
                    path.unlink()
                    stale += 1
                except OSError:
                    pass
        if stale:
            self.startup_notes.append(f"{stale} unfinished query embedding(s) from an earlier run discarded; "
                                      "they embed again on demand")
        return set()

    # ───────── B: one snapshot write per batch, after the turn in flight ─────────
    def _mark_dirty(self):
        if self._dirty_since is None:
            self._dirty_since = self.clock()

    def _persist_allowed(self):
        if self.persist_gate is None:
            return True
        try:
            if self.persist_gate():
                return True
        except Exception:
            return True
        return (self.clock() - self._dirty_since) >= self.persist_delay_s

    def _persist_due_in(self):
        """Seconds until a deferred snapshot write is forced; None when nothing waits."""
        with self._lock:
            if self._dirty_since is None:
                return None
            return max(0.0, round(self.persist_delay_s - (self.clock() - self._dirty_since), 1))

    def unsettled(self):
        """How many ingested jobs still wait for the snapshot write that makes them durable."""
        with self._lock:
            return len(self._ingested)

    def settle(self, force=False):
        """Write the snapshot once for everything ingested since the last write, then mark those jobs
        complete and archive their files. Deferred (False) while persist_gate() reports a turn in flight,
        for at most persist_delay_s; True when nothing waits for a write. No API work."""
        with self._lock:
            if self._dirty_since is None:
                return True
            if not force and not self._persist_allowed():
                return False
            self.model.persist(self.state_path)
            batch, self._ingested, self._dirty_since = self._ingested, [], None
            for path, job in batch:
                job.update(state="complete", completed_at=_now())
                if (job.get("auto_retry") or {}).get("active"):
                    job["auto_retry"] = dict(job["auto_retry"], active=False, recovered_at=job["completed_at"])
                    if self._retry_note == (path.name, self._last_error):
                        # The failure this job's retry announced is resolved and no later error replaced it.
                        self._last_error = self._retry_note = None
                _write(path, job)
                self._archive_job(path, job, write_totals=False)
            if batch:
                _write(self.totals_path, self._totals)
            return True

    def _recover_jobs(self):
        changed, archived = False, 0
        for path in sorted(self.jobs_dir.glob("*.json")):
            job = _read(path)
            if job["state"] in DISPATCH_STATES:
                # A dispatch cut by a restart: retried automatically when enabled, else blocked.
                if self._schedule_retry(path, job, RESTART_ERROR) is None:
                    job.update(state="blocked", error=RESTART_ERROR, blocked_at=_now())
                _write(path, job)
            elif job["state"] == "retry_wait":
                if self.auto_retry["enabled"]:
                    self._retry_due[path.name] = _epoch((job.get("auto_retry") or {}).get("next_due_at"))
                else:
                    # Automatic retry was switched off: the job blocks for the operator, as before.
                    job["auto_retry"] = dict(job.get("auto_retry") or {}, active=False)
                    job.update(state="blocked", blocked_at=_now())
                    _write(path, job)
            event = job["event"]
            existing = self.model.event_by_id.get(event["id"])
            if existing is None:
                self.model.ingest([event], {"facts": []})
                changed = True
            elif existing != event:
                raise ValueError("Journal evidence conflicts with snapshot: " + event["id"])
            if job["state"] == "complete":          # A: finished before the archive folder existed
                self._archive_job(path, job, write_totals=False)
                archived += 1
        if changed:
            self.model.persist(self.state_path)
        if archived:
            _write(self.totals_path, self._totals)
            self.startup_notes.append(f"{archived} finished memory job file(s) moved to jobs/completed")

    def recover_orphans(self):
        """Jobs left in a dispatch state ("extracting", "embedding") while no memory write runs: the worker that held
        them ended without recording an outcome. They count as pending, which refuses the model switch, until the next
        restart recovers them (_recover_jobs); this does the same now (Unlock): retried automatically, else blocked.
        Returns how many; 0 while a memory write is running (its job is not an orphan)."""
        if not self._worker_lock.acquire(blocking=False):
            return 0
        try:
            recovered = 0
            with self._lock:
                if self._closed or self._reset_pending:
                    return 0
                for path in sorted(self.jobs_dir.glob("*.json")):
                    job = _read(path)
                    if job["state"] not in DISPATCH_STATES:
                        continue
                    if self._schedule_retry(path, job, RESTART_ERROR) is None:
                        job.update(state="blocked", error=RESTART_ERROR, blocked_at=_now())
                    _write(path, job)
                    recovered += 1
            return recovered
        finally:
            self._worker_lock.release()

    @staticmethod
    def _public_event(event):
        # Explicit whitelist prevents raw model thoughts or transport metadata
        # from accidentally entering extraction or document embeddings.
        if not isinstance(event, dict):
            raise TypeError("event must be an object")
        if event.get("interrupted") or event.get("cancelled"):
            raise ValueError("Interrupted or cancelled events are not eligible for durable fact extraction")
        if event.get("source_kind", "conversation") != "conversation":
            raise ValueError("Only public conversation events may be archived")
        for name in ("id", "time"):
            if not isinstance(event.get(name), str) or not event[name].strip():
                raise ValueError("event needs nonempty " + name)
        datetime.fromisoformat(event["time"].replace("Z", "+00:00"))
        for name in ("user", "assistant"):
            if not isinstance(event.get(name, ""), str):
                raise TypeError(name + " must be text")
        result = {"id": event["id"], "time": event["time"],
                  "user": event.get("user", ""), "assistant": event.get("assistant", ""),
                  "source_kind": "conversation"}
        # A proactive (open) turn has no user speech; its reflection cue is kept as
        # operator context (event_document labels it "not user speech").
        cue = event.get("cue", "")
        if not isinstance(cue, str):
            raise TypeError("cue must be text")
        if cue.strip():
            result["cue"] = cue
        if not (result["user"].strip() or result["assistant"].strip()):
            raise ValueError("Empty conversation event")
        return result

    def archive(self, event, epoch=None):
        """Archive original evidence now, enqueue enrichment, and make no API calls. epoch: self._wipes when the
        caller read the event; a wipe since then drops it (that conversation was wiped)."""
        public = self._public_event(event)
        ident = _digest(public["id"])
        path = self.jobs_dir / (ident + ".json")
        with self._lock:
            self._require_ready()
            if epoch is not None and epoch != self._wipes:
                return {"id": public["id"], "queued": False, "duplicate": False, "wiped": True}
            existing = self.model.event_by_id.get(public["id"])
            if existing is not None:
                if existing != public:
                    raise ValueError("Conflicting event id: " + public["id"])
                return {"id": public["id"], "queued": False, "duplicate": True}
            if path.exists():
                job = _read(path)
                if job["event"] != public:
                    raise ValueError("Conflicting journal event: " + public["id"])
            else:
                job = {"version": 1, "id": ident, "event": public,
                       "chunk_id": "chunk-live-" + ident[:24], "state": "queued",
                       "created_at": _now(), "embedding_model": self.embedding_model,
                       "dimensions": DIMENSIONS}
                # Journal first: startup can restore the raw event if the process
                # stops before CandidateF's atomic snapshot replacement.
                _write(path, job)
            self.model.ingest([public], {"facts": []})
            self._mark_dirty()
        # B: the snapshot is written once the turn in flight (if any) is over; the journal written above
        # already keeps the event safe (startup restores it).
        self.settle()
        return {"id": public["id"], "queued": True, "duplicate": False}

    def _block(self, path, job, error, epoch=None):
        with self._lock:
            if epoch is not None and epoch != self._wipes:
                return                    # wiped meanwhile: the job went into the backup as it was
            message = f"{type(error).__name__}: {error}"[:500]
            due = self._schedule_retry(path, job, message)
            if due is None:
                job.update(state="blocked", error=message, blocked_at=_now())
            _write(path, job)
            self._last_error = message if due is None else (
                f"{message} (automatic retry {job['auto_retry']['used']}/{self.auto_retry['max_attempts']} "
                f"due {_iso(due)[11:19]} UTC)")
            if due is not None:
                self._retry_note = (path.name, self._last_error)
        if due is not None and self.on_auto_retry is not None:
            with contextlib.suppress(Exception):
                self.on_auto_retry()

    def _schedule_retry(self, path, job, message):
        """Move a job whose provider dispatch failed transiently to "retry_wait" (the caller writes the
        job, holding the state lock or running single-threaded). Returns the due time (epoch seconds), or
        None when the job must block: retry off, a non-transient failure, or no attempt left (exhausted)."""
        record = dict(job.get("auto_retry") or {})
        if not (self.auto_retry["enabled"] and transient_failure(message, job.get("state"))):
            if record.get("active"):
                job["auto_retry"] = dict(record, active=False)
            return None
        used = int(record.get("used") or 0)
        if used >= self.auto_retry["max_attempts"]:
            job["auto_retry"] = dict(record, active=False, exhausted_at=_now())
            return None
        backoff = self.auto_retry["backoff_s"]
        due = self.clock() + backoff[min(used, len(backoff) - 1)]
        attempts = list(record.get("attempts") or [])
        attempts.append({"attempt": used + 1, "error": message, "failed_state": job.get("state"),
                         "failed_at": _now(), "due_at": _iso(due)})
        record.update(attempts=attempts, used=used + 1, active=True, next_due_at=_iso(due))
        record.pop("exhausted_at", None)
        job.update(state="retry_wait", error=message, auto_retry=record)
        job.pop("blocked_at", None)
        self._retry_due[path.name] = due
        return due

    @staticmethod
    def _resume_state(job):
        """The last durable stage a job resumes at; stored results are never rewritten."""
        if job.get("vectors"):
            return "vectors_ready"
        if job.get("embedding_result") is not None:
            return "embedding_received"
        if job.get("facts") is not None:
            return "facts_ready"
        if job.get("extraction_result") is not None:
            return "extraction_received"
        return "queued"

    def _job_scope(self, job):
        hook = self.job_context
        if hook is None:
            return contextlib.nullcontext()
        try:
            return hook((job.get("event") or {}).get("id", ""))
        except Exception:
            return contextlib.nullcontext()

    def _process_job(self, path, epoch=None):
        """One job, resumed at its last durable stage. epoch: self._wipes when the caller listed the job; every write
        below is made under the state lock and only while no wipe happened since (the wipe fence)."""
        with self._lock:
            if epoch is None:
                epoch = self._wipes
            if epoch != self._wipes or not path.exists():
                return False
            job = _read(path)
            state = job["state"]
            if self._closed or state not in {"queued", "extraction_received", "facts_ready",
                                              "embedding_received", "vectors_ready"} \
                    or any(waiting == path for waiting, _ in self._ingested):
                return False

        def fenced():
            return epoch != self._wipes
        try:
            if state == "queued":
                if self.extract_fn is None:
                    return False
                with self._lock:
                    if fenced():
                        return False
                    job.update(state="extracting", extraction_started_at=_now())
                    _write(path, job)
                with self._job_scope(job):
                    result = self.extract_fn([copy.deepcopy(job["event"])], job["chunk_id"])
                if isinstance(result, dict):
                    result = {"facts": result.get("facts"),
                              "rejected": _compact_rejections(result.get("rejected", []))}
                # Persist the callback result before any validation or subsequent
                # billable operation. Root's callback also journals raw HTTP data.
                with self._lock:
                    if fenced():
                        return False
                    job.update(extraction_result=result, state="extraction_received")
                    _write(path, job)
                state = "extraction_received"
            if state == "extraction_received":
                result = job["extraction_result"]
                facts = result.get("facts") if isinstance(result, dict) else result
                if not isinstance(facts, list):
                    raise ValueError("extract_fn must return a facts list")
                if any(not isinstance(fact, dict) or not fact.get("id") for fact in facts):
                    raise ValueError("Every fact needs a globally unique id")
                probe = CandidateF([job["event"]], {"facts": facts})
                accepted_ids = {fact["id"] for fact in probe.facts}
                accepted = [fact for fact in facts if fact["id"] in accepted_ids]
                rejected = _compact_rejections(result.get("rejected", [])) if isinstance(result, dict) else []
                with self._lock:
                    if fenced():
                        return False
                    job.update(facts=accepted, quarantined=rejected + probe.excluded_records, state="facts_ready")
                    _write(path, job)
                state = "facts_ready"
            if state == "facts_ready":
                if self.embed_fn is None:
                    return False
                items = [(job["event"]["id"], event_document(job["event"]))]
                items.extend((fact["id"], record_document(fact)) for fact in job["facts"])
                with self._lock:
                    if self._closed or fenced():
                        return False
                    job.update(state="embedding", embedding_started_at=_now(),
                               embedding_ids=[ident for ident, _ in items])
                    _write(path, job)
                with self._job_scope(job):
                    raw = self.embed_fn([text for _, text in items], "document")
                with self._lock:
                    if fenced():
                        return False
                    job.update(embedding_result=raw, state="embedding_received")
                    _write(path, job)
                state = "embedding_received"
            if state == "embedding_received":
                vectors = _vectors(job["embedding_result"], len(job["embedding_ids"]))
                with self._lock:
                    if fenced():
                        return False
                    job.update(vectors=dict(zip(job["embedding_ids"], vectors)), state="vectors_ready")
                    _write(path, job)
            with self._lock:
                if fenced():
                    return False
                self.model.ingest([job["event"]], {"facts": job["facts"]},
                                  {"documents": job["vectors"], "queries": {}})
                # B: settle() marks the job complete after the snapshot write that holds it.
                self._ingested.append((path, job))
                self._mark_dirty()
            return True
        except Exception as error:
            self._block(path, job, error, epoch)
            return False

    # requests' raise_for_status text for a request the provider rejected outright,
    # e.g. OpenRouter 404 "No endpoints found that satisfy the max price".
    REJECTED_REQUEST = re.compile(r"^HTTPError: 4\d\d ")

    def requeue_blocked(self, *, force=False, max_jobs=None):
        """Re-dispatch blocked jobs whose provider request was rejected before any paid work.

        A ``HTTPError: 4xx`` block means the request never ran, so repeating it cannot
        duplicate a paid stage. Uncertain blocks (timeouts, a process stopped mid-dispatch,
        validation errors) are left alone unless an operator passes ``force``. A job
        resumes at the last durable stage it reached; stored results are never rewritten.
        The caller runs ``flush_pending`` afterwards (nothing is dispatched here). Jobs
        waiting for an automatic retry are not blocked and are left to it; a requeued job
        gets a fresh automatic-retry budget.
        """
        limit = None if max_jobs is None else max(0, int(max_jobs))
        requeued, skipped = [], []
        with self._lock:
            self._require_ready()
            jobs = sorted(((path, _read(path)) for path in self.jobs_dir.glob("*.json")),
                          key=lambda pair: (pair[1]["created_at"], pair[1]["id"]))
            for path, job in jobs:
                if job["state"] != "blocked":
                    continue
                error = str(job.get("error") or "")
                if not force and not self.REJECTED_REQUEST.match(error):
                    skipped.append({"event_id": job["event"]["id"], "error": error})
                    continue
                if limit is not None and len(requeued) >= limit:
                    break
                state = self._resume_state(job)
                history = list(job.get("requeue_history") or [])
                history.append({"error": error, "blocked_at": job.get("blocked_at"), "requeued_at": _now(),
                                "resumed_state": state, "forced": bool(force)})
                job.update(state=state, error=None, requeue_history=history)
                job.pop("blocked_at", None)
                if job.get("auto_retry"):
                    record = {k: v for k, v in job["auto_retry"].items() if k != "exhausted_at"}
                    job["auto_retry"] = dict(record, used=0, active=False)
                _write(path, job)
                requeued.append({"event_id": job["event"]["id"], "resumed_state": state})
        return {"count": len(requeued), "requeued": requeued, "skipped": skipped}

    def flush_pending(self, max_jobs=None):
        """Explicit bounded worker. Blocked jobs are never retried here. A "retry_wait" job whose
        back-off has passed is resumed at its last durable stage (as requeue_blocked(force=True)
        would) when retry_gate allows it, at most `limit` of them per call."""
        limit = self.max_jobs_per_flush if max_jobs is None else max(0, int(max_jobs))
        if not self._worker_lock.acquire(blocking=False):
            return {"busy": True, "attempted": 0, "completed": 0}
        attempted = completed = 0
        try:
            # Asked before the state lock is taken: the gate reads the caller's turn bookkeeping.
            try:
                retry_allowed = self.auto_retry["enabled"] and (self.retry_gate is None or bool(self.retry_gate()))
            except Exception:
                retry_allowed = False
            with self._lock:
                if self._reset_pending:
                    self._require_ready()
                if self._closed:
                    return {"closed": True, "attempted": 0, "completed": 0}
                jobs = sorted(((path, _read(path)) for path in self.jobs_dir.glob("*.json")),
                              key=lambda pair: (pair[1]["created_at"], pair[1]["id"]))
                retried = self._start_due_retries(jobs, limit, retry_allowed)
                ingested = {waiting.name for waiting, _ in self._ingested}
                epoch = self._wipes
            for path, job in jobs:
                if attempted >= limit or epoch != self._wipes:
                    break
                if path.name in ingested or job["state"] not in {"queued", "extraction_received", "facts_ready",
                                                                 "embedding_received", "vectors_ready"}:
                    continue
                attempted += 1
                completed += bool(self._process_job(path, epoch))
            settled = self.settle()
            return {"busy": False, "attempted": attempted, "completed": completed, "retried": retried,
                    "settled": settled}
        finally:
            self._worker_lock.release()

    def _start_due_retries(self, jobs, limit, allowed):
        """Under the state lock: resume up to `limit` due "retry_wait" jobs; re-index the others."""
        now = self.clock()
        self._retry_due = {}
        started = 0
        for path, job in jobs:
            if job["state"] != "retry_wait":
                continue
            record = dict(job.get("auto_retry") or {})
            due = _epoch(record.get("next_due_at"))
            if not allowed or due > now or started >= limit:
                self._retry_due[path.name] = due
                continue
            state = self._resume_state(job)
            attempts = list(record.get("attempts") or [{}])
            attempts[-1] = dict(attempts[-1], started_at=_now(), resumed_state=state)
            record.update(attempts=attempts, active=True)
            record.pop("next_due_at", None)
            job.update(state=state, error=None, auto_retry=record)
            _write(path, job)
            started += 1
            self._auto_retry_dispatched += 1
        return started

    def next_auto_retry_at(self):
        """Epoch seconds of the earliest automatic retry, or None (none waiting / retry off). No disk I/O."""
        with self._lock:
            if not self.auto_retry["enabled"] or self._closed or not self._retry_due:
                return None
            return min(self._retry_due.values())

    def _query_vector(self, query, epoch=None):
        if self.embed_fn is None or not query.strip():
            return None
        key = _digest({"query": query, "model": self.embedding_model, "dimensions": DIMENSIONS})
        path = self.queries_dir / (key + ".json")
        # Serialize cache misses so concurrent identical queries dispatch once.
        with self._query_lock:
            if epoch is not None and epoch != self._wipes:
                return None             # a retrieval from before a wipe: nothing of it goes into the new cache
            if path.exists():
                item = _read(path)
                if item.get("state") == "complete":
                    return item["vector"]
                if item.get("state") == "received":
                    try:
                        vector = _vectors(item["response"], 1)[0]
                        item.update(state="complete", vector=vector, completed_at=_now())
                        _write(path, item)
                        self._query_blocked.discard(path.name)
                        return vector
                    except Exception:
                        pass            # a bad response: embed again below
                # "blocked" (an earlier failure), "dispatching" (a call cut short) or unreadable: ask again —
                # the embedder may well be back; success below clears the blocked mark
            item = {"state": "dispatching", "query": query, "started_at": _now(),
                    "model": self.embedding_model, "dimensions": DIMENSIONS}
            _write(path, item)
            try:
                raw = self.embed_fn([query], "query")
                item.update(state="received", response=raw)
                _write(path, item)
                vector = _vectors(raw, 1)[0]
                item.update(state="complete", vector=vector, completed_at=_now())
                _write(path, item)
                self._query_blocked.discard(path.name)
                return vector
            except Exception as error:
                message = f"{type(error).__name__}: {error}"[:500]
                item.update(state="blocked", error=message)
                _write(path, item)
                self._query_blocked.add(path.name)
                with self._lock:
                    self._last_error = message
                return None

    @staticmethod
    def render(packets, budget_chars):
        """Render one retrieval's candidate packets at another budget (no API work)."""
        return CandidateF.render(packets, budget_chars)

    def retrieve(self, query, exclude_ids=None, now=None, user_name="User", lang="zh"):
        """One retrieval, rendered at this runtime's budget. exclude_ids: event ids still
        in the recent conversation window (dropped without backfill); now / user_name /
        lang: natural-language rendering (perceived times against the caller's clock)."""
        if not isinstance(query, str):
            raise TypeError("query must be text")
        with self._lock:
            self._require_ready()
            empty = not self.model.safe_events
            self._active_retrievals += 1
            epoch = self._wipes
        try:
            vector = None if empty else self._query_vector(query, epoch)
            with self._lock:
                # Query vectors live in their own durable cache. Supply one for
                # this retrieval only, preventing snapshot growth from searches.
                if self.model.vectors is None:
                    self.model.vectors = {"documents": {}, "queries": {}}
                queries = self.model.vectors.setdefault("queries", {})
                previous = queries.get(query)
                if vector is not None:
                    queries[query] = vector
                try:
                    bundle = self.model.retrieve(query, budget_chars=self.budget_chars, now=now,
                                                 user_name=user_name, lang=lang, exclude_ids=exclude_ids,
                                                 fact_packets=self.fact_packets,
                                                 event_candidates=self.event_candidates)
                finally:
                    if previous is None:
                        queries.pop(query, None)
                    else:
                        queries[query] = previous
                self._last_retrieval_degraded = bool(not empty and vector is None)
                bundle["diagnostics"]["runtime_degraded"] = self._last_retrieval_degraded
                bundle["diagnostics"]["runtime_embedding_model"] = self.embedding_model
                return bundle
        finally:
            with self._lock:
                self._active_retrievals -= 1

    def status(self):
        with self._lock:
            # A: finished jobs sit under jobs/completed with their counts in totals.json, so this scan reads
            # only what is still pending. B: a job ingested but not yet written is reported as "ingested".
            counts = {"complete": self._totals["complete"]} if self._totals["complete"] else {}
            blocked, retrying, quarantined = [], [], self._totals["quarantined_facts"]
            totals = {"attempts": self._totals["attempts"], "recovered": self._totals["recovered"], "exhausted": 0}
            ingested = {waiting.name for waiting, _ in self._ingested}
            for path in self.jobs_dir.glob("*.json"):
                job = _read(path)
                state = "ingested" if path.name in ingested else job["state"]
                counts[state] = counts.get(state, 0) + 1
                quarantined += len(job.get("quarantined", []))
                if job["state"] == "blocked":
                    blocked.append({"event_id": job["event"]["id"], "error": job.get("error")})
                record = job.get("auto_retry") or {}
                totals["attempts"] += len(record.get("attempts") or [])
                totals["recovered"] += bool(job["state"] == "complete" and record.get("recovered_at"))
                totals["exhausted"] += bool(job["state"] == "blocked" and record.get("exhausted_at"))
                if record.get("active") and job["state"] not in {"complete", "blocked"}:
                    last = (record.get("attempts") or [{}])[-1]
                    retrying.append({"event_id": job["event"]["id"], "state": job["state"],
                                     "attempt": record.get("used"), "error": last.get("error"),
                                     "next_due_at": record.get("next_due_at")})
            query_blocked = len(self._query_blocked)
            due = [item["next_due_at"] for item in retrying if item["next_due_at"]]
            # A job waiting for an automatic retry is neither pending nor blocked and does not degrade
            # memory; once its attempts are exhausted it is blocked (and degraded) as before.
            return {"method": "F", "events": len(self.model.safe_events),
                    "facts": len(self.model.facts), "job_states": counts,
                    "pending": sum(v for k, v in counts.items() if k not in {"complete", "blocked", "retry_wait", "ingested"}),
                    "unsettled": len(self._ingested), "persist_due_in_s": self._persist_due_in(),
                    "blocked": len(blocked), "blocked_jobs": blocked[-10:],
                    "retrying": len(retrying), "retrying_jobs": retrying[-10:],
                    "auto_retries": {**self.auto_retry, "waiting": counts.get("retry_wait", 0), **totals,
                                     "dispatched": self._auto_retry_dispatched,
                                     "next_due_at": min(due, key=_epoch) if due else None},
                    "quarantined_facts": quarantined,
                    "query_embeddings_blocked": query_blocked,
                    "degraded": bool(self._reset_pending or blocked or query_blocked or self._last_retrieval_degraded
                                     or self.extract_fn is None or self.embed_fn is None),
                    "last_error": self._last_error, "embedding_model": self.embedding_model,
                    "dimensions": DIMENSIONS, "budget_chars": self.budget_chars,
                    "fact_packets": self.fact_packets, "event_candidates": self.event_candidates,
                    "idle_api_calls": False, "closed": self._closed,
                    "reset_pending": self._reset_pending, "seed_disabled": self._last_reset is not None,
                    "last_reset": {key: self._last_reset.get(key) for key in
                                   ("reset_id", "phase", "backup_dir", "completed_at")}
                                  if self._last_reset else None}

    def close(self):
        """Prevent new work; this deliberately never flushes or calls an API. A snapshot write still
        waiting (B) is local and is done now."""
        with self._lock:
            with contextlib.suppress(Exception):
                self.settle(force=True)
            self._closed = True
