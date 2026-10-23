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
- fixer-agent (P15, added 2026-10-23 10:13 CDT on Sayed's order to
  build our own code-fixer): envsafe (NO_PROXY IPv6 sanitizer) +
  backends (mock / codex exec / OpenAI-compatible http for Pitch/
  Micro Ollama) + git-checkpointed fix loop with hard timeouts and
  an honest report — 10 tests green, health HEALTHY. Pitch Codex
  session to wire the real backends is queued in PITCH-QUEUE.md.

## Status at v2 (2026-10-23 14:41 CDT upgrade window, Agent 81)
- completion-agent (P1): manifest.py (binds BOTH real CSV dialects;
  loads the real 113-packet file) + verifier.py (storefront drift,
  named by key, both directions) — the two v1 TODOs are BUILT.
  17 tests green. Still owed for graduation: a verified chunk of 10
  on the real store (Pitch lane, behind the Free-plan cap decision).
- grader-harness (P3): mathcheck.py (duo/pricing consistency proof
  over facts.py) + scoreboard.py (one unified code-health board,
  STALE flagging) — 6 tests green.
- listing-executor (P4, NEW): packets.py validation (verified price/
  compare/sizes, print file must exist) + executor.py (duplicate
  check by title+print file, chunk-of-10, hard-crash resume with no
  double-list, blocked retry after unblock, single-lane token,
  MockAdmin cage driver; the real Fourthwall CDP driver plugs into
  the same protocol on the Pitch) — 7 tests green, health HEALTHY.
  Graduation still requires one real chunk of 10 by the bot alone.
- free-cloud (../free-cloud/): Supabase adapter BUILT (stand-in cage
  tests 5/5); live expansion UNVERIFIED until Sayed's OAuth tap.
- Suite total: 45/45 green (was 26/26 at v1).
