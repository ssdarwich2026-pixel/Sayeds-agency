#!/usr/bin/env python3
"""
ingest_results.py - close out a dispatched batch from its results.

This is the checkpoint's read-back step: after the parent dispatches
a batch on GitHub and downloads the artifacts, feed the result JSONs
(or the batch-summary.json) here. Each job with a result is marked
from the evidence, never from memory:
  status "ok"    -> completed
  status "error" -> error, attempts += 1 (retryable < 3, terminal at 3)
Jobs in the batch with NO result file stay "packed" - they were in
flight when the run ended and are reconciled, not guessed (see
pack_batch.py --release-packed for the wholesale-abort path).

Usage: ingest_results.py --batch-id <id> --results-dir <dir>
                         [--checkpoint checkpoint.json]
"""
import argparse, glob, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import burst_state as bs


def content_problem(job, r):
    """Perplexity's surviving round-table point (2026-10-30): ingest
    used to validate a result's PRESENCE, not its content - an "ok"
    result whose outputs contradict the job definition (e.g. a
    text_pack that silently overwrote files) closed as completed.
    Returns a problem string, or None when the outputs are consistent
    with what the job was asked to produce. Only positive
    contradictions are flagged; unverifiable shapes pass."""
    if job is None or r.get("status") != "ok":
        return None
    out = r.get("outputs")
    if not isinstance(out, dict):
        return "ok result carries no outputs object"
    p = job.get("params", {})
    t = job.get("type")
    if t == "text_pack":
        want = len(p.get("records", []))
        if out.get("records") != want:
            return f"text_pack records {out.get('records')} != job's {want}"
        if len(out.get("files", [])) != want:
            return "text_pack files list does not match record count"
        if not out.get("pack_file"):
            return "text_pack result missing pack_file"
    elif t == "hash_manifest":
        if "entries" in out and out.get("files") != len(out["entries"]):
            return "hash_manifest files count != entries length"
        if not out.get("manifest_file"):
            return "hash_manifest result missing manifest_file"
    elif t == "image_convert":
        if not out.get("output") or not out.get("bytes_out"):
            return "image_convert result missing output/bytes_out"
    elif t == "benchmark":
        b = out.get("benchmark")
        if not isinstance(b, dict) or "tasks_per_min" not in b:
            return "benchmark result missing tasks_per_min"
    elif t == "render":
        if not out.get("video_file") or not out.get("sha256"):
            return "render result missing video_file/sha256"
        if not out.get("duration_s"):
            return "render result missing duration_s"
        floor = p.get("min_duration_s")
        if floor and float(out["duration_s"]) < float(floor):
            return (f"render duration {out['duration_s']}s below job "
                    f"floor {floor}s")
        want_channel = p.get("channel_id")
        if want_channel and out.get("channel_id") != want_channel:
            return "render result channel label mismatch"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--results-dir", required=True)
    ap.add_argument("--queue", default=str(HERE / "queue.jsonl"))
    ap.add_argument("--checkpoint", default=str(HERE / "checkpoint.json"))
    args = ap.parse_args()

    jobs = bs.load_queue(args.queue)
    by_id = {j["id"]: j for j in jobs}
    ckpt = bs.load_checkpoint(args.checkpoint, jobs)
    if args.batch_id not in ckpt["batches"]:
        print(f"batch {args.batch_id} not in checkpoint - nothing to ingest")
        return 1

    results = {}
    for f in glob.glob(str(Path(args.results_dir) / "**" / "*.json"),
                       recursive=True):
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        if isinstance(d, dict) and "job_id" in d and "status" in d:
            results[d["job_id"]] = d

    closed, still_packed = [], []
    for jid in ckpt["batches"][args.batch_id]["job_ids"]:
        rec = ckpt["jobs"][jid]
        if rec["disposition"] != "packed":
            continue
        r = results.get(jid)
        if r is None:
            still_packed.append(jid)
            continue
        rec["result"] = r
        problem = content_problem(by_id.get(jid), r)
        if r["status"] == "ok" and problem is None:
            rec["disposition"] = "completed"
        elif r["status"] == "ok":
            rec["disposition"] = "error"
            rec["attempts"] += 1
            rec["note"] = f"content check failed: {problem}"
        else:
            rec["disposition"] = "error"
            rec["attempts"] += 1
            rec["note"] = r.get("error")
        closed.append((jid, rec["disposition"]))
    bs.save_checkpoint(args.checkpoint, ckpt)
    print(f"batch {args.batch_id}: closed {len(closed)} jobs -> {closed}")
    print(f"still packed (no result read back, NOT guessed): {still_packed}")
    print("checkpoint counts:", bs.counts(ckpt),
          "| next_unprocessed_index:", ckpt["next_unprocessed_index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
