#!/usr/bin/env python3
"""
burst_batch_summary.py - reconciled batch summary for burst-batch.yml.

82's reverify accounting (2026-10-30): the summary reports FOUR
separate counts - expected / successful / failed / missing - because
a fully-accounted batch WITH failures is COMPLETE-BUT-UNSUCCESSFUL,
not "incomplete", and a per-item failure must not fail the summary
job (the dispatcher's failure model: one bad job never kills the
batch; ingest_results.py is the system of record that closes jobs).

  complete         = every expected index accounted for exactly once
                     (missing empty, no unreadable result files)
  successful_batch = complete AND failed == 0
  exit code        = 1 iff NOT complete (a hole in the evidence),
                     0 when complete - successful or not.

Env: BATCH_ID, EXPECTED (from the setup job). Reads burst-result-*.json
in the cwd and writes batch-summary.json in the cwd.
"""
import glob, json, os, sys


def main():
    bid = os.environ.get("BATCH_ID", "")
    raw = os.environ.get("EXPECTED", "")
    if not raw.isdigit():
        json.dump({"batch_id": bid, "expected": None, "complete": False,
                   "successful_batch": False,
                   "fatal": "setup job produced no count"},
                  open("batch-summary.json", "w"), indent=1)
        print("FATAL: setup outputs missing - cannot reconcile")
        return 1
    expected = int(raw)
    results, unreadable = [], 0
    for f in sorted(glob.glob("burst-result-*.json")):
        try:
            results.append(json.load(open(f)))
        except Exception as e:
            unreadable += 1
            print(f"UNREADABLE result file {f}: {e}")
    ok = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] != "ok"]
    got = sorted(r["index"] for r in results)
    missing = sorted(set(range(expected)) - set(got))
    duplicated = sorted({i for i in got if got.count(i) > 1})
    complete = (not missing and not duplicated and unreadable == 0
                and len(results) == expected)
    summary = {"batch_id": bid, "expected": expected,
               "reported": len(results),
               "successful": len(ok), "failed": len(err),
               "missing": missing, "duplicated": duplicated,
               "unreadable": unreadable,
               "complete": complete,
               "successful_batch": complete and not err,
               "results": results}
    json.dump(summary, open("batch-summary.json", "w"), indent=1)
    for r in results:
        print(f"{r['index']:>3} {r['job_id']:<16} {r['type']:<14} "
              f"{r['status']:<6} {r['metrics']['elapsed_s']}s")
    print(f"BATCH {bid}: expected {expected} / reported {len(results)} "
          f"/ successful {len(ok)} / failed {len(err)} "
          f"/ missing {missing} / complete={complete} "
          f"/ successful_batch={summary['successful_batch']}")
    if not complete:
        print("RECONCILIATION FAILED - evidence has a hole; "
              "ingest_results.py remains the system of record")
        return 1
    if err:
        print("COMPLETE-BUT-UNSUCCESSFUL: every job accounted for; "
              "per-item failures are recorded, not hidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
