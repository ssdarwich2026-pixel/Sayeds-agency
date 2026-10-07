# GroupMe Bot Gateway — the agency's office intercom

**What this is, in plain words:** right now Sayed's GroupMe HQ groups are a
*notepad* — reports land there. This turns them into an *office*: Sayed types
in the group, the bot hears it, does something, and answers back in the
thread. Same idea as those WhatsApp agents everyone talks about — except
GroupMe has an official, free bot API, so there's no hacky bridge and no
ban risk.

## What each file does

| File | Plain-words job |
|---|---|
| `server.py` | The receptionist. Listens for GroupMe's knocks, checks the secret password, hands messages to the brain, posts answers back. |
| `webhook_logic.py` | The bouncer's rulebook. Decides what's worth answering — most importantly, **never answer the bot's own messages** (that would be an infinite loop of the bot talking to itself). No internet needed; this is what the test exercises. |
| `agent.py` | The Phase 1 brain. A dispatcher with 4 working skills: `help`, `status`, `note`, `remember`. Comments inside mark exactly where Phase 2 plugs in LiteLLM/OpenRouter so each job can run on a *different* AI model. |
| `run.sh` | One-command starter: `./run.sh`. |
| `requirements.txt` | The 3 Python packages needed (`pip install -r requirements.txt`). |
| `.env.example` | The blank form. Copy to `.env` and fill in your secrets — the real `.env` is **never** committed. |
| `groupme-bot.service` | Keeps the bot alive 24/7 on a VPS (systemd). Only needed for the always-on deployment. |
| `test_dryrun.py` | The safety drill: `python3 test_dryrun.py` proves the self-reply guard and all 4 skills work, with zero GroupMe involved. |

## Going live — Sayed's checklist (his hands only)

**Step 1 — Create the bot (2 minutes, his GroupMe account):**
1. Go to https://dev.groupme.com/bots and sign in with the GroupMe account.
2. "Create Bot" → pick the HQ group it should live in → give it a name and avatar.
3. Copy the **bot_id** it shows you. That's the bot's posting pass — paste it
   into `.env` as `GROUPME_BOT_ID`. (Posting needs only the bot_id, no token.)

**Step 2 — Host the server (pick one):**
- *Try it (free, 5 minutes):* on any computer, run `./run.sh`, then in another
  terminal run `cloudflared tunnel --url http://localhost:8000`. Cloudflare
  prints a public `https://...` URL — free, no account needed.
- *Always-on (a few $/mo):* a cheap VPS + the included `groupme-bot.service`
  file (install steps are commented at the top of that file), then point a
  domain or the server's IP at it with HTTPS.

**Step 3 — Connect them:** back on https://dev.groupme.com/bots, set the bot's
**Callback URL** to `https://YOUR-HOST/webhook/YOUR-CALLBACK-SECRET`
(the secret is the long random string from your `.env`).

**Step 4 — Test:** type `help` in the group. The bot should answer with its
skill list. Then try `note testing the office intercom`.

**Step 5 — Repeat Step 1+3** for each HQ group that should have the bot
(NFT Launch HQ, SHiPTrOLLYARD HQ, AI Video Lab, Agency…).

## Security notes (short, important)

- The callback URL **is** the password: anyone who knows the full URL
  (including the secret part) can make the bot talk. Keep it private, like
  any password. Unknown secrets get an instant 403.
- GroupMe does not sign its callbacks, so the secret-in-URL is the standard
  protection — this is what the code implements.
- The server never logs message text, only who wrote and in which group.
- `.env` (with the bot_id and secret) is git-ignored. Secrets stay in
  Sayed's hands; the agent never stores them anywhere else.

## GroupMe API facts that shaped this build

- Bots are **group-scoped** — they live in groups, not DMs. (Sayed's HQ
  groups are all groups, so this fits perfectly.)
- Posting is `POST https://api.groupme.com/v3/bots/post` with
  `{"bot_id": "...", "text": "..."}` — no auth token required.
- Incoming callbacks include `sender_type` (`"user"` vs `"bot"`) and a
  `system` flag — the code ignores both bot and system messages.
- Keep messages under ~3,000 characters (the code chunks long replies at
  2,900 to stay safe — learned from GroupMe web choking on long pastes).

## Phase 1 vs Phase 2

- **Phase 1 (this code):** keyword dispatcher, 4 real skills, runs anywhere
  Python runs. Honest label: role-based skeleton, one brain.
- **Phase 2:** swap the dispatcher for LiteLLM/OpenRouter calls so the bot
  understands plain sentences and each skill can run on a *different* model
  (Claude for writing, DeepSeek for code, Kimi for research…). The skills
  don't change — only the dispatcher gets smarter. See the `PHASE 2 NOTE`
  comment at the top of `agent.py`.
