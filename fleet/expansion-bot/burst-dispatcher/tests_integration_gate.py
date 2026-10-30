#!/usr/bin/env python3
"""
tests_integration_gate.py - the #12 INTEGRATION REGRESSION GATE
(82's reverify, 2026-10-30). NO chunking rollout until this passes.

End-to-end on scratch copies: queue -> pack -> runner (local) ->
results -> ingest -> checkpoint state, proving the two properties
the whole design exists for:
  1. MISSING STAYS MISSING - a job with no result read back stays
     "packed" (never completed, never guessed), and
  2. DUPLICATE RECEIPTS DON'T DOUBLE-CLOSE - ingesting the same
     results twice changes nothing the second time.
Plus: a per-item error closes as error with attempts incremented,
and a later honest result for a previously-missing job closes it.

Exit 0 = GATE PASS. Runs in a temp dir; live files never touched.
"""
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cli(script, *args, cwd):
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, cwd=str(cwd))
    if r.returncode != 0:
        print("CLI FAILED:", script, args, r.stdout, r.stderr)
        raise SystemExit(1)
    return r.stdout


def main():
    tmp = Path(tempfile.mkdtemp(prefix="burst-gate-"))
    failures = []
    try:
        for f in ("burst_state.py", "pack_batch.py", "ingest_results.py",
                  "burst_runner.py"):
            shutil.copy(HERE / f, tmp / f)
        (tmp / "queue.jsonl").write_text("\n".join([
            '{"id": "gate-ok", "type": "text_pack", "lane": "any",'
            ' "params": {"template": "A {v}", "records": [{"v": 1}]}}',
            '{"id": "gate-err", "type": "image_convert", "lane": "any",'
            ' "params": {"input": "does-not-exist.png", "format": "jpg"}}',
            '{"id": "gate-lost", "type": "text_pack", "lane": "any",'
            ' "params": {"template": "B", "records": [{}]}}',
        ]) + "\n")
        ck = str(tmp / "ck.json")
        q = str(tmp / "queue.jsonl")
        bid = "batch-20261030-424"

        cli(tmp / "pack_batch.py", "--queue", q, "--checkpoint", ck,
            "--repo", str(tmp), "--n", "3", "--lane", "any",
            "--batch-id", bid, cwd=tmp)
        manifest = json.loads((tmp / "batches" / f"{bid}.json").read_text())

        # Run jobs 0 (ok) and 1 (per-item error); job 2's result is
        # "lost in transit" - it never reaches the results dir.
        resdir = tmp / "results"
        resdir.mkdir()
        for idx in (0, 1):
            cli(tmp / "burst_runner.py", "--manifest",
                str(tmp / "batches" / f"{bid}.json"), "--index", str(idx),
                "--out", str(resdir / f"burst-result-{idx}.json"),
                "--workdir", str(tmp), cwd=tmp)

        out = cli(tmp / "ingest_results.py", "--batch-id", bid,
                  "--results-dir", str(resdir), "--queue", q,
                  "--checkpoint", ck, cwd=tmp)
        state = json.loads(Path(ck).read_text())["jobs"]
        if state["gate-ok"]["disposition"] != "completed":
            failures.append(f"gate-ok not completed: {state['gate-ok']}")
        if not (state["gate-err"]["disposition"] == "error"
                and state["gate-err"]["attempts"] == 1):
            failures.append(f"gate-err wrong: {state['gate-err']}")
        if state["gate-lost"]["disposition"] != "packed":
            failures.append(
                f"MISSING DID NOT STAY MISSING: {state['gate-lost']}")

        # Duplicate ingest: same receipts again - nothing may change.
        before = Path(ck).read_text()
        cli(tmp / "ingest_results.py", "--batch-id", bid,
            "--results-dir", str(resdir), "--queue", q,
            "--checkpoint", ck, cwd=tmp)
        after = json.loads(Path(ck).read_text())["jobs"]
        for jid in ("gate-ok", "gate-err", "gate-lost"):
            if after[jid]["disposition"] != state[jid]["disposition"] \
                    or after[jid]["attempts"] != state[jid]["attempts"]:
                failures.append(f"DUPLICATE INGEST CHANGED {jid}: "
                                f"{state[jid]} -> {after[jid]}")

        # The lost job's result finally arrives: it closes honestly.
        cli(tmp / "burst_runner.py", "--manifest",
            str(tmp / "batches" / f"{bid}.json"), "--index", "2",
            "--out", str(resdir / "burst-result-2.json"),
            "--workdir", str(tmp), cwd=tmp)
        cli(tmp / "ingest_results.py", "--batch-id", bid,
            "--results-dir", str(resdir), "--queue", q,
            "--checkpoint", ck, cwd=tmp)
        final = json.loads(Path(ck).read_text())["jobs"]
        if final["gate-lost"]["disposition"] != "completed":
            failures.append(f"gate-lost did not close on arrival: "
                            f"{final['gate-lost']}")

        if failures:
            print("GATE FAIL:")
            for f in failures:
                print(" -", f)
            return 1
        print("GATE PASS: missing stayed missing, duplicate receipts "
              "did not double-close, error closed with attempt, "
              "late result closed honestly")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
