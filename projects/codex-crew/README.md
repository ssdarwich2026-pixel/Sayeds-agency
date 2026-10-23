# codex-crew — the 8 code projects (Sayed's orders, 2026-10-23)

**Build route (changed 2026-10-23 07:30 CDT, Sayed: "Make the next
moves going forward"):** the Door workers returned 10/10 products
with zero code — they answer, they cannot write files. So the code
is written by Agent 81 directly in this repo (VM), deployed to the
Oracle Micro (~/system-agent/codex-crew/), and the worker crew
supplies what it is proven at: specs, fixtures, test cases, and
grading material. Sayed adds projects as he sees the need; new
projects enter through the 811-lead backlog (P9–P12 standing).

## Run
- All tests: `python3 run_tests.py` (writes each project's status.json)
- Per project health: `python3 <project>/health.py` (exit 0 = healthy)
- Plant: the Micro heartbeat reads each project's status.json
  (mirrored to ~/system-agent/codex-crew-status/) every 5 minutes.

## Status at v1 (2026-10-23, Agent 81)
- grader-harness (P3): facts.py + grader.py (10 rules covering every
  Wave 1 failure class) + health + tests — 3 test methods, all
  PASS/FAIL fixtures green.
- completion-agent (P1): ledger.py (evidence-gated state machine) +
  queue.py (chunk-of-10 + finish audit) + health — 8 tests green.
  Still to build: manifest.py parser binding, storefront verifier.
- campaign-driver (P2): core.py (VERIFIED-LIVE handshake, grader
  blocker, featured order, mock day builder) + health — 5 tests
  green. Still to build: platform adapters, metrics collector.
- Wave 2 (P4–P8): enter build in dependency order as Wave 1
  modules complete; same route (81 writes, workers supply inputs).
