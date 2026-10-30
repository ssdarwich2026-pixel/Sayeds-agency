#!/usr/bin/env python3
"""
check_sync.py - automated byte-equivalence check for the burst
dispatcher copies (mandatory rule from 82's reverify, 2026-10-30:
every patch lands in BOTH copies, verified, never assumed).

Pairs (repo copy <-> fleet source-pack copy):
  tools/burst_runner.py            <-> burst-dispatcher/burst_runner.py
  tools/pack_batch.py              <-> burst-dispatcher/pack_batch.py
  tools/burst_state.py             <-> burst-dispatcher/burst_state.py
  tools/burst_batch_summary.py     <-> burst-dispatcher/burst_batch_summary.py
  .github/workflows/burst-batch.yml <-> burst-dispatcher/burst-batch.yml
  .github/workflows/burst-benchmark.yml <-> burst-actions-workflow.yml
      (benchmark pair: headers differ by design - compared from the
      first "name:" line onward)

Exit 0 = all pairs equivalent. Run before every dispatcher commit.
"""
import sys
from pathlib import Path

AGENCY = Path.home() / "workspace" / "agency"
FLEET = AGENCY / "fleet" / "expansion-bot"
DISP = FLEET / "burst-dispatcher"

PAIRS = [
    (AGENCY / "tools" / "burst_runner.py", DISP / "burst_runner.py", False),
    (AGENCY / "tools" / "pack_batch.py", DISP / "pack_batch.py", False),
    (AGENCY / "tools" / "burst_state.py", DISP / "burst_state.py", False),
    (AGENCY / "tools" / "burst_batch_summary.py",
     DISP / "burst_batch_summary.py", False),
    (AGENCY / ".github" / "workflows" / "burst-batch.yml",
     DISP / "burst-batch.yml", False),
    (AGENCY / ".github" / "workflows" / "burst-benchmark.yml",
     FLEET / "burst-actions-workflow.yml", True),
]


def body(text, from_name_line):
    if not from_name_line:
        return text
    lines = text.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.startswith("name:"):
            return "".join(lines[i:])
    return text


def main():
    bad = 0
    for a, b, partial in PAIRS:
        ta = body(a.read_text(), partial)
        tb = body(b.read_text(), partial)
        same = ta == tb
        print(("OK  " if same else "DIFF"), a.relative_to(AGENCY),
              "<->", b.relative_to(AGENCY))
        bad += 0 if same else 1
    print("SYNC:", "ALL EQUIVALENT" if not bad else f"{bad} PAIR(S) DIFFER")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
