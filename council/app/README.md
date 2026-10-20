# Jury of Five App — Room 1

A small, phone-first web app that wraps the Jury of Five engine
(`council/jury.py`) so Sayed can ask questions and read verdicts without a
terminal. Single Python service, standard library only (`http.server`) —
no new dependencies, no build step, no database.

## Run it (one command)

From the repo root:

```sh
cd ~/workspace/agency
JURY_APP_PASSCODE="pick-a-passcode" python3 council/app/server.py
```

Then open **http://127.0.0.1:8765** on this machine.

- Mock / demo mode ($0, instant, no live calls — for testing):

```sh
JURY_APP_PASSCODE="pick-a-passcode" JURY_APP_MOCK=1 python3 council/app/server.py
```

- Mock via the engine variable instead (equivalent):

```sh
JURY_APP_PASSCODE="pick-a-passcode" \
  JURY_ENGINE_CMD="python3 council/mock_jury.py" \
  python3 council/app/server.py
```

## Env vars

| Var | Default | Meaning |
|---|---|---|
| `JURY_APP_PASSCODE` | *(unset)* | If set, the app is gated behind this passcode (simple form + cookie session; a wrong passcode gets a plain-language refusal). **If unset, the gate is DISABLED** — the app prints a warning at startup and shows a warning banner, and anyone who can reach the address can use the jury. Set it. |
| `JURY_ENGINE_CMD` | `python3 council/jury.py` | The engine to invoke for each Ask. `.py` paths are resolved against the repo root, then the council dir, so `python3 council/jury.py` and `python3 council/mock_jury.py` both work from anywhere. |
| `JURY_APP_MOCK` | *(unset)* | `1` = use the mock engine (`council/mock_jury.py`) and include `council/mock-runs/` in History, unless `JURY_ENGINE_CMD` is set explicitly. |
| `JURY_APP_PORT` | `8765` | Port to listen on. |
| `JURY_APP_HOST` | `127.0.0.1` | Bind address. Localhost only by default — this app is served privately to the owner's devices, never exposed to the public internet by default. |

## How it works

- **Ask** — one question at a time. Submitting starts the engine as a
  background job and returns a job id; the page polls `/api/job/<id>`
  every 3 seconds and shows friendly stages — "Asking the five…" →
  "Cross-checking…" → "Verdict" — then jumps to the verdict. The HTTP
  request never blocks on a run (a live run takes ~1–3 minutes).
- **Verdict view** — the agreed answer first and large, then who answered
  (a partial panel of 3–4 is a valid result, and the page says so),
  each juror's answer in collapsible sections, the disagreements,
  the confidence note, and the escalation block last — in a copyable
  box when the jury says escalate.
- **History** — lists `council/runs/*.md`, newest first (question +
  date); in mock mode it also lists `council/mock-runs/*.md`. Read-only:
  the app never edits or deletes run logs. Tapping an entry opens the
  same verdict view.
- **Jury of 45+ tab** — placeholder only ("In the works"). Its engine
  is a later brief.

## Budget line

The Ask page shows today's remaining free-request budget, read live on
every page load from the same connector budget tool the engine uses —
the `openrouter.budget_py` path in `council/config.yaml`, invoked as
`python3 <budget_py> status` (falling back to `check 0`). The number is
never hard-coded. If the tool can't be read, the page shows a
plain-language "budget unavailable" line instead of a fake number.

## Safety

- The app never displays, logs, or transmits the OpenRouter credential.
  It only invokes the engine as a subprocess, exactly like a terminal;
  the engine resolves its own credential via the Secure Vault connector.
- All errors are shown in plain language; no stack traces in the UI.
- $0 rule intact: no paid APIs, no new services, `:free` models only
  (enforced by the engine/config, untouched by this app).

## Smoke test

```sh
python3 council/app/smoke_test.py
```

Boots the app in mock mode on a scratch port with a test passcode and
checks: passcode gate (including wrong-passcode refusal), Ask page,
budget line, Jury of 45+ placeholder, a full mock Ask → poll → verdict
with **all** sections present (a launch/contract question, so the
escalation packet is exercised), History listing, and opening a past
verdict. Exit 0 = PASS. Makes no live calls and spends no budget.

## Files

- `server.py` — the whole service (server + inline UI).
- `smoke_test.py` — the test above.
- No changes to `council/jury.py` or `council/config.yaml`.
