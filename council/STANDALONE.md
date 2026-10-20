# Jury of Five — Model 2 (Standalone)

## What this is

**Model 1** is the Jury app that runs with Muse (Agent 81): Muse's
machine holds the keys, the budget counter, and the app itself.

**Model 2 — this branch (`jury-standalone`) — is the same jury with zero
Muse dependency.** Same questions, same five advisors, same verdict
format, same app. The only differences are three small fallbacks:

1. Instead of Muse's credential vault, it uses **your own OpenRouter
   key**, read from an environment variable.
2. Instead of Muse's budget tool, it keeps its own daily counter on
   disk (`council/.budget-local.json`, 50 free requests/day — same cap).
3. It can run on your computer or on a free cloud host under **your**
   accounts.

**When to use it:** Muse is gone, unreachable, or you just want the jury
in your own hands. Until then, Model 1 is the primary — nothing changes.

---

## Your one secret: your own OpenRouter key

The jury only ever calls **`:free` models** — that's enforced in the
code — so the key needs **no money on it at all**.

1. Go to **openrouter.ai** and sign in (or create a free account).
2. Open **Keys → Create Key**. Name it something like `jury-standalone`.
3. Set its credit limit to **$0** (free models only).
4. Copy the key — **this is the secret.**
   - **Never paste it in a chat, a text, or an email.**
   - Only ever put it in two places: your hosting site's secret/env
     settings (Route B), or an environment variable / `.env` file on
     your own computer (Route A).
   - If it ever leaks: delete that key on openrouter.ai and make a new
     one. Two minutes, done.

---

## Route A — run it on your own computer

You need: your computer, internet, about 10 minutes.

1. **Get the code** (in a terminal):
   ```
   git clone -b jury-standalone https://github.com/ssdarwich2026-pixel/Sayeds-agency.git
   cd Sayeds-agency
   ```
   (No git? On the GitHub page for the repo, switch the branch dropdown
   to `jury-standalone`, then **Code → Download ZIP**, and unzip it.)
2. **Install Python 3** if you don't have it: from
   **python.org/downloads** (Windows/Mac) — then check:
   ```
   python3 --version
   ```
3. **Install the one extra package:**
   ```
   pip install pyyaml
   ```
4. **Set your key** (paste your key where it says PASTE-YOUR-KEY —
   in your own terminal only, never in chat):
   - Mac / Linux:
     ```
     export OPENROUTER_API_KEY="PASTE-YOUR-KEY"
     ```
   - Windows (PowerShell):
     ```
     $env:OPENROUTER_API_KEY = "PASTE-YOUR-KEY"
     ```
   Optionally also set a passcode for the app:
   `export JURY_APP_PASSCODE="pick-a-word"` (same idea on Windows).
5. **Start the app:**
   ```
   python3 council/app/server.py
   ```
6. **Open it:** **http://127.0.0.1:8765** in your browser. Ask away.

**Use it from your phone on the same Wi-Fi:** start it with the host
setting opened up, then open the same address with your computer's
local IP instead of 127.0.0.1 (e.g. `http://192.168.1.20:8765`):

```
JURY_APP_HOST=0.0.0.0 python3 council/app/server.py
```

(Set a `JURY_APP_PASSCODE` if you do this — anyone on your Wi-Fi could
otherwise open it. Accessibility is your call; the passcode is cheap
insurance.)

**Notes for Route A:** the computer must be on and the command left
running while you use the jury. Past verdicts collect in
`council/runs/` as files. The daily budget counter lives in
`council/.budget-local.json` — delete it and the count restarts.

---

## Route B — free cloud host, always-on link (recommended backup)

Use **Render** (render.com). Why this one: its free web-service tier is
real and needs **no credit card**, it deploys straight from your GitHub,
and it allows outbound calls to OpenRouter. (Railway and Fly.io no
longer have a real free tier; PythonAnywhere's free tier blocks calls
to sites it hasn't whitelisted, which would break the jury.)

Free-tier reality: the app **sleeps after ~15 minutes idle** and takes
about a minute to wake on the next tap. Past verdicts and the budget
counter are stored on the service's disk and **can reset when Render
redeploys or restarts the service** — the jury still works, history
just starts fresh. Good enough for a backup; Model 1 keeps the full
history.

1. Create a free account at **render.com** (sign up with GitHub is
   easiest).
2. **New → Web Service →** connect your GitHub and pick the repo
   **`ssdarwich2026-pixel/Sayeds-agency`**, branch **`jury-standalone`**.
3. Settings:
   - **Runtime / Language:** Python 3
   - **Build command:** `pip install pyyaml`
   - **Start command:** `JURY_APP_HOST=0.0.0.0 python3 council/app/server.py`
   - **Instance type:** Free
4. **Environment variables** (in Render's Environment section — this is
   one of the two safe places for your key):
   - `OPENROUTER_API_KEY` = your key from openrouter.ai (see above)
   - `JURY_APP_PASSCODE` = a word you pick — **do set this one**: a
     cloud link is open to the internet, and without a passcode anyone
     with the link can spend your daily free budget.
   (Render sets the `PORT` variable itself; this branch's app reads it
   automatically — nothing for you to do.)
5. Click **Create Web Service**. First build takes a few minutes.
   Render gives you a link like `https://your-jury.onrender.com` —
   **that's your always-on jury.** Bookmark it on your phone.

---

## Quick checks

- **"No way to sign in to OpenRouter…"** — the key isn't set. Set
  `OPENROUTER_API_KEY` (Route A step 4 / Route B step 4) and restart.
- **Budget shows fewer requests than you expect** — a full question
  uses about 6 requests (5 advisors + 1 judge, plus retries). The cap
  is 50/day and resets at midnight.
- **First tap after a while is slow on Render** — it's just waking up.
  Give it a minute and refresh.
- **The app asks for a passcode** — that's `JURY_APP_PASSCODE`. If you
  never set one and it still asks, someone/something else set it;
  unset it and restart.
