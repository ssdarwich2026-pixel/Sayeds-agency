#!/usr/bin/env python3
"""
drain_local.py - run the burst queue's LOCAL subset on this VM.

Same queue + checkpoint logic as the burst lane, for jobs that should
not burst (tiny, local-only, or while GitHub is unreachable). It runs
each packable local job through the identical runner the Actions
shards use (imported from the repo copy at ~/workspace/agency/tools/
burst_runner.py, so local and burst results are directly comparable),
records the disposition per item as it lands, and saves the
checkpoint after every job - a crash or a dropped session leaves the
in-flight item unrecorded, ready for the resume pass to reconcile.

Judging matches ingest_results.py exactly, including the content
verification of "ok" results (an ok whose outputs contradict the job
definition closes as an error + attempt, never completed).

--tiny-only (P12/#14): drains hash_manifest + text_pack jobs (lanes
local or either) in a small process pool (2 workers - the VM's core
count), checkpointing after each completion as it lands. Tiny jobs
should never wait on a GitHub round-trip.

Usage: drain_local.py [--queue queue.jsonl] [--checkpoint checkpoint.json]
                      [--limit N] [--tiny-only]
"""
import argparse, importlib.util, json, sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import burst_state as bs

REPO = Path.home() / "workspace" / "agency"
TINY_TYPES = ("hash_manifest", "text_pack")


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "burst_runner", REPO / "tools" / "burst_runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_content_problem():
    spec = importlib.util.spec_from_file_location(
        "ingest_results", HERE / "ingest_results.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.content_problem


def _run_job(payload):
    manifest, index = payload
    return load_runner().run_one(manifest, index, REPO)


def judge(job, result, content_problem):
    """(disposition, note) - mirrors ingest_results.py exactly."""
    if result["status"] == "ok":
        problem = content_problem(job, result)
        if problem is None:
            return "completed", None
        return "error", f"content check failed: {problem}"
    return "error", result.get("error")


def apply(ckpt, job, result, content_problem, batch_tag):
    rec = ckpt["jobs"][job["id"]]
    rec["result"] = result
    disp, note = judge(job, result, content_problem)
    rec["disposition"] = disp
    if disp == "completed":
        rec["batch_id"] = batch_tag
    else:
        rec["attempts"] += 1
        rec["note"] = note
    return disp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", default=str(HERE / "queue.jsonl"))
    ap.add_argument("--checkpoint", default=str(HERE / "checkpoint.json"))
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--tiny-only", action="store_true",
                    help="drain tiny job types (hash_manifest, "
                         "text_pack; lanes local/either) in a "
                         "2-process pool")
    args = ap.parse_args()

    jobs = bs.load_queue(args.queue)
    ckpt = bs.load_checkpoint(args.checkpoint, jobs)
    print("checkpoint before drain:", bs.counts(ckpt),
          "| resume index:", ckpt["next_unprocessed_index"])
    content_problem = load_content_problem()
    fake_manifest = {"batch_id": "local-drain", "jobs": jobs}
    done = 0

    if args.tiny_only:
        todo = []
        for job in jobs:
            if done + len(todo) >= args.limit:
                break
            if job["type"] not in TINY_TYPES:
                continue
            if job.get("lane", "either") not in ("local", "either"):
                continue
            if bs.is_packable(ckpt["jobs"][job["id"]]):
                todo.append(job)
        if todo:
            import multiprocessing as mp
            with ProcessPoolExecutor(
                    max_workers=2,
                    mp_context=mp.get_context("fork")) as ex:
                futs = {ex.submit(_run_job,
                                  (fake_manifest, job["_index"])): job
                        for job in todo}
                for fut in as_completed(futs):
                    job = futs[fut]
                    result = fut.result()
                    disp = apply(ckpt, job, result, content_problem,
                                 "local-drain")
                    bs.save_checkpoint(args.checkpoint, ckpt)
                    print(f"  [{job['_index']}] {job['id']}: {disp}")
                    done += 1
        print(f"drained {done} tiny jobs (pool of 2)")
    else:
        runner = load_runner()
        for job in jobs:
            if done >= args.limit:
                break
            if job.get("lane", "either") != "local":
                continue
            rec = ckpt["jobs"][job["id"]]
            if not bs.is_packable(rec):
                continue
            result = runner.run_one(fake_manifest, job["_index"], REPO)
            disp = apply(ckpt, job, result, content_problem,
                         "local-drain")
            bs.save_checkpoint(args.checkpoint, ckpt)  # per item
            print(f"  [{job['_index']}] {job['id']}: {disp}")
            done += 1
        print(f"drained {done} local jobs")
    print("checkpoint after drain:", bs.counts(ckpt),
          "| next_unprocessed_index:", ckpt["next_unprocessed_index"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
