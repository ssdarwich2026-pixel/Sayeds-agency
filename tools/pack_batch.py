#!/usr/bin/env python3
"""
pack_batch.py - pack the next N pending burst-queue jobs into a batch.

Reads the JSONL queue + the checkpoint state record, takes the next N
packable jobs in stable queue order (never a completed / terminal-error
/ skipped job, never a job already packed - so a re-run after a crash
packs only what is genuinely still owed), writes a batch manifest to
<repo>/batches/<batch-id>.json (the copy the GitHub workflow reads)
plus a mirror copy beside this script, and marks the jobs "packed" in
the checkpoint. The checkpoint is saved atomically as one step with
the manifest write; if the process dies between them, the resume rule
applies: a manifest on disk whose jobs are not marked packed is
reconciled by re-running the packer (it will re-use the same batch id
only if told to; by default it creates the next id and the orphan
manifest is simply never dispatched).

Reconciliation for infrastructure aborts (a whole workflow run died):
  pack_batch.py --release-packed <batch-id>
returns that batch's packed-but-unresulted jobs to "pending" so the
next pack includes them again. Jobs with results already ingested are
never released.

Usage:
  pack_batch.py [--queue queue.jsonl] [--checkpoint checkpoint.json]
                [--repo ~/workspace/agency] [--n 20]
                [--lane burst|local|any] [--batch-id ID]
  pack_batch.py --release-packed <batch-id> [...]
"""
import argparse, json, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import burst_state as bs

HERE = Path(__file__).resolve().parent
DEFAULT_REPO = Path.home() / "workspace" / "agency"


def lane_matches(job, lane):
    job_lane = job.get("lane", "either")
    if lane == "any":
        return True
    if lane == "burst":
        return job_lane in ("burst", "either")
    if lane == "local":
        return job_lane in ("local", "either")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(HERE / "queue.jsonl"))
    ap.add_argument("--checkpoint", default=str(HERE / "checkpoint.json"))
    ap.add_argument("--repo", default=str(DEFAULT_REPO))
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--lane", default="burst", choices=["burst", "local", "any"])
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--chunk-size", type=int, default=8,
                    help="P12: max jobs per runner leg (chunked "
                         "sharding); heavy jobs always solo")
    ap.add_argument("--no-chunk", action="store_true",
                    help="emit a v1 manifest (one job per leg)")
    ap.add_argument("--release-packed", default=None, metavar="BATCH_ID")
    args = ap.parse_args()

    jobs = bs.load_queue(args.queue)
    ckpt = bs.load_checkpoint(args.checkpoint, jobs)
    by_id = {j["id"]: j for j in jobs}

    if args.release_packed:
        bid = args.release_packed
        released, poisoned = [], []
        for jid, rec in ckpt["jobs"].items():
            if rec["disposition"] == "packed" and rec["batch_id"] == bid:
                if rec.get("packs", 0) >= bs.MAX_ATTEMPTS:
                    # Poison-job guard: packed MAX_ATTEMPTS times, never
                    # produced a result - its leg dies deterministically
                    # before writing one (OOM/timeout), so ingest could
                    # never increment attempts. Terminal, loudly noted.
                    rec["disposition"] = "error"
                    rec["attempts"] = bs.MAX_ATTEMPTS
                    rec["batch_id"] = None
                    rec["note"] = (
                        f"poison-job guard: packed {rec.get('packs', 0)}x "
                        f"with no result ever read back (last in {bid}) - "
                        f"leg dies before writing a result; terminal")
                    poisoned.append(jid)
                    continue
                rec["disposition"] = "pending"
                rec["batch_id"] = None
                rec["note"] = f"released from {bid} by reconcile pass"
                released.append(jid)
        bs.save_checkpoint(args.checkpoint, ckpt)
        print(f"released {len(released)} packed jobs from {bid}: {released}")
        if poisoned:
            print(f"POISON-JOB GUARD: {len(poisoned)} jobs marked "
                  f"terminal-error (packed {bs.MAX_ATTEMPTS}x, no result): "
                  f"{poisoned}")
        print("checkpoint counts:", bs.counts(ckpt),
              "| next_unprocessed_index:", ckpt["next_unprocessed_index"])
        return 0

    print("checkpoint before pack:", bs.counts(ckpt),
          "| resume index (next_unprocessed_index):",
          ckpt["next_unprocessed_index"])

    selected = []
    for job in jobs:  # stable queue order; checkpoint decides eligibility
        if len(selected) >= args.n:
            break
        rec = ckpt["jobs"][job["id"]]
        if bs.is_packable(rec) and lane_matches(job, args.lane):
            selected.append(job)

    if not selected:
        print("nothing packable - queue fully packed/completed for lane",
              args.lane)
        bs.save_checkpoint(args.checkpoint, ckpt)
        return 0

    ckpt["batch_seq"] += 1
    batch_id = args.batch_id or datetime.now(timezone.utc).strftime(
        "batch-%Y%m%d") + f"-{ckpt['batch_seq']:03d}"
    manifest = {
        "batch_id": batch_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "pack_batch.py",
        "lane": args.lane,
        "count": len(selected),
        "jobs": [{k: v for k, v in j.items() if not k.startswith("_")}
                 for j in selected],
    }
    if not args.no_chunk:
        # P12 chunked sharding: consecutive light jobs share a leg up
        # to --chunk-size; a heavy job (flagged, or a benchmark by
        # nature) always gets a solo leg and breaks the current group.
        chunks, cur = [], []
        for pos, job in enumerate(selected):
            heavy = job.get("heavy") is True or job["type"] == "benchmark"
            if heavy:
                if cur:
                    chunks.append(cur)
                    cur = []
                chunks.append([pos])
            else:
                cur.append(pos)
                if len(cur) >= max(1, args.chunk_size):
                    chunks.append(cur)
                    cur = []
        if cur:
            chunks.append(cur)
        manifest["chunks"] = [{"chunk": i, "job_indices": idxs}
                              for i, idxs in enumerate(chunks)]

    repo_manifest = Path(args.repo) / "batches" / f"{batch_id}.json"
    repo_manifest.parent.mkdir(parents=True, exist_ok=True)
    repo_manifest.write_text(json.dumps(manifest, indent=1))
    local_manifest = HERE / "batches" / f"{batch_id}.json"
    local_manifest.parent.mkdir(parents=True, exist_ok=True)
    local_manifest.write_text(json.dumps(manifest, indent=1))

    for job in selected:
        rec = ckpt["jobs"][job["id"]]
        rec["disposition"] = "packed"
        rec["batch_id"] = batch_id
        rec["packs"] = rec.get("packs", 0) + 1
        rec["note"] = None
    ckpt["batches"][batch_id] = {
        "created_at": manifest["created_at"],
        "job_ids": [j["id"] for j in selected],
        "manifest_repo_path": str(repo_manifest),
    }
    bs.save_checkpoint(args.checkpoint, ckpt)

    print(f"packed {len(selected)} jobs -> {batch_id}")
    for j in selected:
        print("  ", j["_index"], j["id"], j["type"])
    if "chunks" in manifest:
        print(f"chunks: {len(manifest['chunks'])} leg(s): "
              f"{[c['job_indices'] for c in manifest['chunks']]}")
    print("manifest (repo):", repo_manifest)
    print("manifest (local mirror):", local_manifest)
    print("checkpoint after pack:", bs.counts(ckpt),
          "| next_unprocessed_index:", ckpt["next_unprocessed_index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
