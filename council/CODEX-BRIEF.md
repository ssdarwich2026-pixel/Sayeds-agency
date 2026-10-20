# CODEX BRIEF — Jury of Five App (Room 1)

**From:** Agent 81 (Muse) · **For:** Codex (Agent 82's build channel) · **Date:** 2026-10-20
**Repo:** ssdarwich2026-pixel/Sayeds-agency · **Work in:** `council/app/` · **Owner of final call:** Sayed

## Mission

Build a small, phone-first web app that wraps the existing **Jury of Five** engine so one
non-technical user (Sayed) can ask questions and read verdicts without a terminal.
The engine already works — **do not rewrite it**. Your job is the door, not the engine room.

## What already exists (read these first)

- `council/jury.py` — the engine. CLI: `python3 jury.py run "<question>"` runs the full
  jury and writes a markdown run log; `python3 jury.py probe` health-checks the models.
  It fans a question out to 5 models, cross-checks them with a judge model, and emits a
  structured verdict (agreed answer / disagreements / confidence / escalation call).
- `council/config.yaml` — models, judge, prompts, limits. **Hard rule enforced there:
  only `:free` OpenRouter model IDs, ever.** The OpenRouter credential is resolved by the
  engine via the Secure Vault connector — never embed, print, or handle any API key.
- `council/README.md` — the five seats, live probe log (2026-10-20), and the free-tier
  limits (429s are routine; a run may seat only 3–5 jurors; NVIDIA returns HTTP 200 with
  error bodies; a clean run costs ~6 requests of a ~50/day free budget).
- `council/runs/*.md` — past run logs. The app reads these for history. The canonical
  sample is `runs/2026-10-20-101024-for-a-print-on-demand-shirt.md` — use it as your
  rendering fixture.

## Build: `council/app/`

A single Python service (stdlib `http.server` preferred; Flask only if already present —
no new paid or heavy dependencies, no build step, no database).

### Pages / behavior

1. **Ask screen (home)**
   - Title: "Jury of Five".
   - A line showing today's remaining free-request budget (read it the same way the
     engine does — via the connector budget tool referenced in `config.yaml`; do not
     hard-code a number).
   - One large textarea + one "Ask the Jury" button. One question at a time.
2. **Running state** — a jury run takes roughly 1–3 minutes. Start the run as a
   background job, return a job id, and have the page poll a status endpoint every few
   seconds. Show friendly stages: "Asking the five…" → "Cross-checking…" → "Verdict".
   Never block the HTTP request on the run.
3. **Verdict screen** — render the run's markdown log with this hierarchy:
   - The **agreed answer** first, large and plain.
   - Then **who answered** (which jurors seated; a partial panel of 3–4 is a valid
     result, not an error — say so plainly).
   - Collapsible: each juror's individual answer (labeled by seat/provider),
     the disagreements and how they were resolved, the confidence note.
   - The **escalation block** last: if the jury says "escalate", show its escalation
     packet (refined question + findings + open disagreements) in a copyable box.
4. **History** — list `council/runs/*.md`, newest first (question + date). Tapping one
   opens the same verdict view. Read-only; never edit or delete run logs.
5. **Room 2 tab** — a second tab labeled "Jury of 45+" with a simple "In the works"
   placeholder. No functionality. (Its engine is a later brief.)

### Access & safety

- Single user. Gate the app behind a passcode read from env var `JURY_APP_PASSCODE`
  (simple form + cookie session is fine). No accounts, no sign-up.
- Bind to localhost / a private interface only — this service is served privately to
  the owner's devices, never exposed to the public internet by default.
- The app must never display, log, or transmit the OpenRouter credential. It only ever
  invokes the engine.
- All errors in plain language (e.g., "The free pool is busy — only 3 of 5 jurors
  answered. That's still a valid verdict."). No stack traces in the UI.

### Testing requirements

- **Mock engine provided:** `council/mock_jury.py` is a soft-pass mimic of the real
  engine — same CLI (`run "<question>"`, `probe`), same run-log format, instant and
  $0, logs to `council/mock-runs/`. Point the app's engine command at it via an env
  var (e.g. `JURY_ENGINE_CMD="python3 council/mock_jury.py"`, defaulting to
  `jury.py`) for all build and UI tests — the free budget is precious (~50/day,
  shared) and live calls are never part of a build. Its canned verdict exercises
  every section, including the escalation packet when a question mentions a launch,
  money, or a contract.
- Smoke test: app boots, serves the ask page, mock verdict renders with all sections,
  history lists existing runs. Provide it as `council/app/smoke_test.py` or a shell
  script and make it pass.
- Do not run live jury calls as part of the build.

### Deliverables

- `council/app/` — server + static UI (single service, runs with one command).
- `council/app/README.md` — exact run command, port, env vars (`JURY_APP_PASSCODE`,
  `JURY_APP_MOCK`), and how history/budget are sourced.
- No changes to `jury.py` or `config.yaml` behavior. If the engine needs a tweak to be
  callable from the app, propose it in the PR description — don't silently change it.

## Done criteria

- [ ] One command starts the app; ask page loads on a phone-sized screen, cleanly.
- [ ] Mock Ask → verdict view shows answer, panel, disagreements, confidence,
      escalation block — all sections present.
- [ ] History lists the existing runs and opens them read-only.
- [ ] Budget line reflects the real counter (not hard-coded).
- [ ] Passcode gate works; wrong passcode gets a plain-language refusal.
- [ ] Jury of 45+ tab shows the placeholder.
- [ ] Smoke test passes; README complete.
- [ ] $0 rule intact: no paid APIs, no new services, `:free` models only.

## Context (why this exists)

Sayed runs a small AI agency on a $0-spend doctrine. The Jury of Five is tier 1 of a
two-tier decision system: the Five handle everyday questions and triage what escalates
to the In-Depth Crew (tier 2, the "Jury of 45+", a later brief). This app is Room 1.
Keep it simple enough that he never needs help to use it.
