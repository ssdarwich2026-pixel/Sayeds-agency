# P15 FIXER — our own code-fixing program

Sayed, 2026-10-23 10:13 CDT: "Can we draft the codes to make these
programs ourselves in Codex from the Pitch and build it, being that we
have the idea and we know where we will run into issues?"

YES. We do not clone OpenHands/OpenCode. We build the lean fixer the
Code-Fix Pipeline actually needs, on model routes WE control, with
every cage-test lesson baked in as a design rule. Enters via the
811-lead backlog under Sayed's add-on rule (P13 Design Scout and P14
Pricing Optimizer came from Launch Intelligence; this is P15).

## What it is
A stdlib-only Python program: INTENT packet + failing tests in →
investigate → propose a diff → apply in a git-checkpointed cage →
re-run tests → loop or stop → report with the test output and the
diff. A fix is FIXED only when the project's own tests pass.
Labels: BUILT → TEST-PASSED → LIVE, never blended.

## Known issues → design rules (the whole point)
1. **Model wall (Zen free exhausted / external-free forbidden / no
   keys on the VM).** Backends are pluggable and OURS:
   - `codex` — subprocess to a logged-in Codex CLI (`codex exec`,
     read-only sandbox, diff-only output). Primary on the Pitch,
     whose Codex path is located:
     C:\Users\NJE Financial LLC\.codex\plugins\.plugin-appserver\codex.exe
   - `http` — OpenAI-compatible endpoint (Pitch/Micro Ollama
     qwen3:8b, $0, keyless, on-box; or the agency gateway later).
   - `mock` — deterministic, for tests and dry runs.
   No Zen, no external free tiers — real code never leaves our routes.
2. **OpenCode hangs after a fatal model error.** Every backend call
   has a hard timeout, its process is killed on expiry, and backend
   errors surface verbatim in the report as BACKEND-ERROR / TIMEOUT.
   The fixer NEVER hangs and NEVER swallows an error.
3. **VM NO_PROXY IPv6 entries break LiteLLM/httpx ("Invalid port:
   ':1]'").** `envsafe.sanitize_env()` strips IPv6 entries from
   NO_PROXY/no_proxy for every subprocess and HTTP call we spawn.
4. **No Docker on the VM.** The cage is a git checkpoint: HEAD is
   recorded before any change; a run that never passes restores the
   workdir and saves the failed diff to the report. Nothing outside
   the workdir is touched; test commands are explicit, never
   model-invented.
5. **RAM / Expansion-50.** Stdlib only, one fix run at a time per
   node, bounded context (capped file sizes, capped test output),
   bounded attempts (default 3) with no-progress detection.
6. **Essays are not fixes (Wave 1 lesson).** The backend contract is
   a unified diff or nothing. Unparseable output = a failed attempt,
   counted, never applied partially.

## Build route
Drafted by Agent 81 in this repo (Build-Route Switch, 2026-10-23
07:30) and tested on the VM. The Pitch Codex session then extends
and verifies it where the Codex login + Ollama live — one prepped
session, queued behind revenue in PITCH-QUEUE.md. Workers supply
fixtures / named test cases / grading material only.

## v1 scope (this draft)
envsafe + backends (mock / codex / http) + fix loop + report +
health + tests. v2 candidates: Micro deployment + plant heartbeat,
Aider-trial interop (the Micro Aider/qwen3:8b trial already running),
grader-harness integration so fixed worker products re-grade
automatically.
