#!/usr/bin/env python3
"""
tests_regression.py - correctness regression suite for the burst
dispatcher (mandatory rule from 82's reverify, 2026-10-30: every
correctness patch ships with a regression test).

Covers: P1 jpeg normalize - P4 validator (dup ids, negative index,
bad batch id, runner-side validation) - P5 text_pack collisions -
P8 hash file-match + symlink escape - P9 out_dir containment -
poison-job guard - ingest content verification - summary accounting
(complete / successful / failed / missing as separate counts).

Runs entirely on scratch copies in a temp dir; the live checkpoint
and queue are never touched. Exit 0 = all pass.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path.home() / "workspace" / "agency" / "tools"))

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


def run_cli(script, *args, cwd):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, cwd=str(cwd))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="burst-regression-"))
    try:
        import burst_runner as br
        import ingest_results as ir

        # scratch workdir with a tiny image
        from PIL import Image
        Image.new("RGB", (24, 18), (10, 120, 200)).save(tmp / "in.png")
        (tmp / "adir").mkdir()

        def manifest(jobs, bid="batch-20261030-777"):
            return {"batch_id": bid, "jobs": jobs}

        # P1: format "jpeg" converts (was a guaranteed KeyError crash)
        m = manifest([{"id": "img-1", "type": "image_convert",
                       "params": {"input": "in.png", "format": "jpeg"}}])
        r = br.run_one(m, 0, tmp)
        check("P1 jpeg converts", r["status"] == "ok"
              and r["outputs"]["format"] == "jpg", str(r))

        # P4: validator - duplicate ids, runner-side
        m2 = manifest([{"id": "x", "type": "text_pack",
                        "params": {"template": "t", "records": []}},
                       {"id": "x", "type": "text_pack",
                        "params": {"template": "t", "records": []}}])
        try:
            br.run_one(m2, 0, tmp)
            check("P4 dup ids rejected by runner", False, "no raise")
        except ValueError:
            check("P4 dup ids rejected by runner", True)
        # P4: bad batch id
        try:
            br.validate_manifest(manifest([], bid="nope"))
            check("P4 bad batch id rejected", False, "no raise")
        except ValueError:
            check("P4 bad batch id rejected", True)
        # P4: negative index via CLI exits 2
        (tmp / "m.json").write_text(json.dumps(
            manifest([{"id": "ok-1", "type": "text_pack",
                       "params": {"template": "t", "records": []}}])))
        rc = run_cli(HERE.parent.parent.parent / "tools" / "burst_runner.py"
                     if False else Path.home() / "workspace" / "agency"
                     / "tools" / "burst_runner.py",
                     "--manifest", str(tmp / "m.json"), "--index", "-1",
                     cwd=tmp)
        check("P4 negative index exits 2", rc.returncode == 2,
              rc.stderr[:80])

        # P5: collisions rejected before any write
        m3 = manifest([{"id": "tp-1", "type": "text_pack",
                        "params": {"template": "hi {n}",
                                   "file_pattern": "{n}.txt",
                                   "records": [{"n": "a"}, {"n": "a"}]}}])
        r = br.run_one(m3, 0, tmp)
        check("P5 collision is per-item error",
              r["status"] == "error" and "collision" in r["error"], str(r))
        m4 = manifest([{"id": "tp-2", "type": "text_pack",
                        "params": {"template": "x",
                                   "file_pattern": "pack.txt",
                                   "records": [{}]}}])
        r = br.run_one(m4, 0, tmp)
        check("P5 pack.txt reserved", r["status"] == "error", str(r))

        # P8: directory-only pattern = missing -> error by default
        m5 = manifest([{"id": "hm-1", "type": "hash_manifest",
                        "params": {"paths": ["adir"]}}])
        r = br.run_one(m5, 0, tmp)
        check("P8 dir-only pattern errors", r["status"] == "error", str(r))
        # P8/P9: symlink escaping the workdir is never read or counted
        (tmp / "link.txt").symlink_to("/etc/hostname")
        m6 = manifest([{"id": "hm-2", "type": "hash_manifest",
                        "params": {"paths": ["link.txt"]}}])
        r = br.run_one(m6, 0, tmp)
        check("P9 symlink escape not hashed", r["status"] == "error",
              str(r))

        # P9: out_dir containment - escaping job id raises before mkdir
        try:
            br.out_dir(tmp, "../evil")
            check("P9 out_dir escape rejected", False, "no raise")
        except ValueError:
            check("P9 out_dir escape rejected", True)

        # Batch #4 regression (2026-10-30): the workflow invokes the
        # runner with workdir "." - a RELATIVE path. Every earlier
        # test used absolute temp dirs, so the suite passed while the
        # live runners failed on relative_to("."). Test the real
        # invocation shape: chdir into the scratch dir, workdir ".".
        old_cwd = os.getcwd()
        os.chdir(tmp)
        try:
            m7 = manifest([{"id": "hm-rel", "type": "hash_manifest",
                            "params": {"paths": ["in.png"]}}])
            r = br.run_one(m7, 0, ".")
            check("Batch#4 regression: hash_manifest with workdir='.'",
                  r["status"] == "ok", str(r))
            m8 = manifest([{"id": "tp-rel", "type": "text_pack",
                            "params": {"template": "z {a}",
                                       "records": [{"a": 1}]}}])
            r = br.run_one(m8, 0, ".")
            check("Batch#4 regression: text_pack with workdir='.'",
                  r["status"] == "ok", str(r))
            m9 = manifest([{"id": "img-rel", "type": "image_convert",
                            "params": {"input": "in.png",
                                       "format": "jpeg"}}])
            r = br.run_one(m9, 0, ".")
            check("Batch#4 regression: image_convert with workdir='.'",
                  r["status"] == "ok", str(r))
        finally:
            os.chdir(old_cwd)

        # Poison-job guard + content verification (scratch checkpoint)
        for f in ("burst_state.py", "pack_batch.py", "ingest_results.py"):
            shutil.copy(HERE / f, tmp / f)
        (tmp / "queue.jsonl").write_text(
            '{"id": "pj-1", "type": "text_pack", "lane": "burst",'
            ' "params": {"template": "x", "records": [{}]}}\n')
        ck = str(tmp / "ck.json")
        for i in (1, 2, 3):
            bid = f"batch-20261030-8{i:02d}"
            run_cli(tmp / "pack_batch.py", "--queue", str(tmp / "queue.jsonl"),
                    "--checkpoint", ck, "--repo", str(tmp), "--n", "1",
                    "--batch-id", bid, cwd=tmp)
            run_cli(tmp / "pack_batch.py", "--queue", str(tmp / "queue.jsonl"),
                    "--checkpoint", ck, "--release-packed", bid, cwd=tmp)
        rec = json.loads(Path(ck).read_text())["jobs"]["pj-1"]
        check("poison-job guard terminal at 3 packs",
              rec["disposition"] == "error" and rec["attempts"] == 3,
              str(rec))

        job = {"id": "g-1", "type": "text_pack",
               "params": {"template": "y", "records": [{}, {}]}}
        bad = {"status": "ok", "outputs": {"records": 5,
               "files": ["a"], "pack_file": "p"}}
        good = {"status": "ok", "outputs": {"records": 2,
                "files": ["a", "b"], "pack_file": "p"}}
        check("content check flags doctored ok",
              ir.content_problem(job, bad) is not None)
        check("content check passes honest ok",
              ir.content_problem(job, good) is None)

        # Summary accounting: complete-but-unsuccessful is complete
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bbs", Path.home() / "workspace" / "agency" / "tools"
            / "burst_batch_summary.py")
        bbs = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bbs)
        sdir = tmp / "sumtest"
        sdir.mkdir()
        for i, st in ((0, "ok"), (1, "error")):
            (sdir / f"burst-result-{i}.json").write_text(json.dumps(
                {"job_id": f"j-{i}", "type": "text_pack", "index": i,
                 "status": st, "metrics": {"elapsed_s": 0.1}}))
        old = os.getcwd()
        os.chdir(sdir)
        try:
            os.environ.update(BATCH_ID="batch-20261030-777", EXPECTED="2")
            rc = bbs.main()
            summ = json.loads((sdir / "batch-summary.json").read_text())
            check("summary: complete-but-unsuccessful exits 0",
                  rc == 0 and summ["complete"] is True
                  and summ["successful_batch"] is False
                  and summ["successful"] == 1 and summ["failed"] == 1
                  and summ["missing"] == [], str(summ))
            (sdir / "burst-result-1.json").unlink()
            rc = bbs.main()
            summ = json.loads((sdir / "batch-summary.json").read_text())
            check("summary: missing index exits 1, named missing",
                  rc == 1 and summ["missing"] == [1], str(summ))
        finally:
            os.chdir(old)

        print(f"\nREGRESSION: {len(PASS)} passed, {len(FAIL)} failed")
        return 1 if FAIL else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
