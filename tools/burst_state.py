#!/usr/bin/env python3
"""
burst_state.py - checkpoint state record for the burst dispatcher queue.

Implements the checkpointed-bulk-operations pattern:
- One state record for the whole queue, created before the first item runs.
- Every job gets a stable index (its position in the queue file) and id.
- Fixed disposition set, written as each job reaches it:
    pending          - no record yet / returned to the pool
    packed           - in a batch manifest, not yet resulted (in flight)
    completed        - a result read-back proved it landed OK
    error            - the job itself failed; retryable while attempts < 3,
                       terminal at attempts >= 3 (never re-packed after)
    skipped          - deliberately not run, with a reason
- Infrastructure failures (dead transport, dead session, wholesale
  workflow failure) are NOT per-item dispositions: an in-flight item
  stays "packed" and unresulted, and a resume pass reconciles it
  (see pack_batch.py --release-packed) instead of guessing.
- Every save is atomic (tmp file + os.replace) and happens after every
  disposition change, so a crash mid-pass loses nothing already recorded.
"""
import json, os, tempfile
from pathlib import Path

MAX_ATTEMPTS = 3
DISPOSITIONS = ("pending", "packed", "completed", "error", "skipped")


def load_queue(queue_path):
    jobs = []
    for line in Path(queue_path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        job = json.loads(line)
        job["_index"] = len(jobs)
        jobs.append(job)
    return jobs


def new_checkpoint(jobs):
    return {
        "version": 1,
        "next_unprocessed_index": 0,
        "batch_seq": 0,
        "jobs": {},      # id -> {index, disposition, batch_id, attempts, note, result}
        "batches": {},   # batch_id -> {created_at, job_ids, manifest}
    }


def load_checkpoint(ckpt_path, jobs):
    p = Path(ckpt_path)
    if p.exists():
        ckpt = json.loads(p.read_text())
    else:
        ckpt = new_checkpoint(jobs)
    # Register any queue jobs not yet known (queue grew since last run).
    known = set(ckpt["jobs"])
    for job in jobs:
        if job["id"] not in known:
            ckpt["jobs"][job["id"]] = {
                "index": job["_index"], "disposition": "pending",
                "batch_id": None, "attempts": 0, "packs": 0,
                "note": None, "result": None,
            }
    refresh_next_index(ckpt)
    return ckpt


def refresh_next_index(ckpt):
    """Resume pointer: first queue index whose job has no terminal record."""
    terminal = []
    for rec in ckpt["jobs"].values():
        if is_terminal(rec):
            terminal.append(rec["index"])
    nxt = 0
    while nxt in terminal:
        nxt += 1
    ckpt["next_unprocessed_index"] = nxt


def is_terminal(rec):
    if rec["disposition"] == "completed" or rec["disposition"] == "skipped":
        return True
    if rec["disposition"] == "error" and rec["attempts"] >= MAX_ATTEMPTS:
        return True
    return False


def is_packable(rec):
    """A job may be (re)packed iff it never landed and still has retries.
    Poison-job guard (2026-10-30, round-table find): a job packed
    MAX_ATTEMPTS times with no result ever read back is NOT packable -
    its leg dies before writing a result (OOM/timeout), so ingest can
    never bump its attempts; without this guard release+repack loops
    forever. pack_batch.py marks such jobs terminal-error on release."""
    if rec["disposition"] == "pending":
        return rec.get("packs", 0) < MAX_ATTEMPTS
    if rec["disposition"] == "error" and rec["attempts"] < MAX_ATTEMPTS:
        return True
    return False


def save_checkpoint(ckpt_path, ckpt):
    refresh_next_index(ckpt)
    p = Path(ckpt_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(ckpt, f, indent=1, sort_keys=True)
    os.replace(tmp, p)


def counts(ckpt):
    out = {d: 0 for d in DISPOSITIONS}
    for rec in ckpt["jobs"].values():
        out[rec["disposition"]] = out.get(rec["disposition"], 0) + 1
    return out
