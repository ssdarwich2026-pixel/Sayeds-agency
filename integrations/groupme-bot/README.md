# GroupMe Bot Gateway — the agency's office intercom

**What this is, in plain words:** right now Sayed's GroupMe HQ groups are a
*notepad* — reports land there. This turns them into an *office*: Sayed types
in the group, the bot hears it, does something, and answers back in the
thread. Same idea as those WhatsApp agents everyone talks about — except
GroupMe has an official, free bot API, so there's no hacky bridge and no
ban risk.

**How the bot listens (the review council's verdict): POLLING.** Every
5 minutes a tiny script asks GroupMe "anything new in my groups?" and
answers what it finds. No public server, no always-on hosting, no
webhook URL — it runs on the workers we already have, for $0. The
trade: replies land within ~5 minutes instead of instantly. (The old
webhook server is still here as the low-latency alternative — see below.)

## What each file does

| File | Plain-words job |
|---|---|
| `poll.py` | **The primary transport (polling).** Asks GroupMe for new messages, filters them, claims each one *before* answering (so a crash can never cause a double-reply), runs the brain, posts answers back. No server needed. |
| `poll_once.py` | One poll cycle across all groups — this is what cron runs every 5 minutes. Exits 0 on success, 1 on failure so the scheduler can detect problems. |
| `server.py` | The webhook alternative (low-latency). Listens for GroupMe's knocks instead of asking. Only needed if ~5-minute replies aren't fast enough. |
| `webhook_logic.py` | The bouncer's rulebook, shared by both transports. Decides what's worth answering — most importantly, **never answer the bot's own messages** (that would be an infinite loop of the bot talking to itself). Also the shared message chunker (bot posts cap at **1,000 chars**, verified). No internet needed; this is what the tests exercise. |
| `agent.py` | The Phase 1 brain. A dispatcher with 4 working skills: `help`, `status`, `note`, `remember`. Comments inside mark exactly where Phase 2 plugs in LiteLLM/OpenRouter so each job can run on a *different* AI model. |
| `run.sh` | One-command starter for the webhook server: `./run.sh`. (Not needed for polling.) |
| `requirements.txt` | The 3 Python packages needed (`pip install -r requirements.txt`). |
| `.env.example` | The blank form. Copy to `.env` and fill in your secrets — the real `.env` is **never** committed. |
| `groupme-bot.service` | Keeps the webhook server alive 24/7 on a VPS (systemd). Only needed for the always-on webhook deployment. |
| `test_dryrun.py` | The original safety drill: `python3 test_dryrun.py` proves the self-reply guard and all 4 skills work, with zero GroupMe involved. |
| `test_poll.py` | The polling safety drill: `python3 test_poll.py` proves pagination, the crash-safety (exactly-once), the reply cap, and the chaos drill — all with zero GroupMe involved. |

## Going live — Sayed's checklist (his hands only)

**Step 1 — Create the bot(s) (2 minutes, his GroupMe account):**
1. Go to https://dev.groupme.com/bots and sign in with the GroupMe account.
2. "Create Bot" → pick the HQ group it should live in → give it a name and avatar.
3. Copy the **bot_id** it shows you. That's the bot's posting pass — paste it
   into `.env`. (Posting needs only the bot_id, no token.)
4. Repeat for each HQ group that should have the bot (NFT Launch HQ,
   SHiPTrOLLYARD HQ, AI Video Lab, Agency…). Each group gets its own bot_id.

**Step 2 — Get the user token (3 minutes, his GroupMe account):**
The poller reads messages *as you*, so it needs your OAuth token (the bot
API alone can't read groups).
1. Go to https://dev.groupme.com/applications and sign in.
2. "Create Application" — name it e.g. "Sayeds Agency". The callback URL
   can be anything (e.g. `https://localhost`) since you'll copy the token
   by hand.
3. Visit `https://oauth.groupme.com/oauth/authorize?client_id=YOUR_CLIENT_ID`
   (replace with the real client ID), sign in, tap **Authorize**.
4. Your browser lands on the callback URL with `?access_token=XXXX`
   appended — copy that token into `.env` as `GROUPME_USER_TOKEN`.
5. It is **long-lived** (no expiry unless you revoke it) and it is a
   **full-account credential**: it can read every group and act as you.
   `.env` / GitHub Secrets only — never chat, logs, or screenshots.
   (If anything on those pages looks different from these steps, follow
   the page — GroupMe occasionally renames buttons.)

**Step 3 — Map groups to bots:** in `.env`, set
`GROUPS_JSON={"<group_id>": "<bot_id>", ...}` with one entry per group.
(To find a group_id: open the group on web.groupme.com — it's the number
in the URL. Single-group shortcut: set `GROUP_IDS` + `GROUPME_BOT_ID` instead.)

**Step 4 — Schedule it (the "always-on" part, $0):**
Polling needs no server — just a timer. On the machine that runs the
agency workers, add to the crontab (`crontab -e`):
```
*/5 * * * * cd /opt/sayeds-agency/integrations/groupme-bot && /usr/bin/python3 poll_once.py >> poll.log 2>&1
```
Add `MAILTO=you@example.com` at the top of the crontab and cron will
email you whenever a cycle fails (nonzero exit) — that's the dead-man's
switch. Replies land within ~5 minutes of you writing.

**Step 5 — Test:** type `help` in the group. Within 5 minutes the bot
should answer with its skill list. Then try `note testing the office
intercom`.

**Alternative — webhook (instant replies):** if ~5 minutes isn't fast
enough, the webhook server path still works: host `server.py`
(`./run.sh` locally, or the `groupme-bot.service` file on a VPS behind
HTTPS), then on https://dev.groupme.com/bots set the bot's **Callback
URL** to `https://YOUR-HOST/webhook/YOUR-CALLBACK-SECRET`. Same skills,
same brain — just instant instead of every-5-minutes.

## Security notes (short, important)

- The **user token is a full-account credential**: whoever holds it can
  read all your groups and act as you. It lives in `.env` / GitHub
  Secrets only — never in chat, logs, screenshots, or pasted anywhere
  else. If it ever leaks, revoke it at dev.groupme.com/applications and
  make a new one.
- The **bot_id** is only a posting pass for that one group — much less
  sensitive, but still keep it in `.env`, not in chat.
- The poller sends the token **only** in the `X-Access-Token` header —
  never in the URL (URLs end up in logs and caches). The test suite
  verifies this.
- (Webhook alternative:) the callback URL **is** the password: anyone who
  knows the full URL (including the secret part) can make the bot talk.
  Keep it private. Unknown secrets get an instant 403.
- GroupMe does not sign its callbacks, so the secret-in-URL is the standard
  protection for the webhook path — this is what that code implements.
- Neither transport logs message text — only who wrote and in which group.
- `.env` (with the bot_id, token, and secret) is git-ignored. Secrets stay
  in Sayed's hands; the agent never stores them anywhere else.

## GroupMe API facts that shaped this build

- Bots are **group-scoped** — they live in groups, not DMs. (Sayed's HQ
  groups are all groups, so this fits perfectly.)
- Posting is `POST https://api.groupme.com/v3/bots/post` with
  `{"bot_id": "...", "text": "..."}` — no auth token required.
- Reading is `GET https://api.groupme.com/v3/groups/<id>/messages`
  with `?after_id=<last_seen>&limit=100` and the user token in the
  **`X-Access-Token` header** (never the URL). `after_id` — not
  `since_id` — is the correct pagination cursor; ids compare as integers,
  monotonically increasing.
- Bot-posted messages cap at **1,000 characters** (verified) — the shared
  chunker splits long replies at 990 to stay safe. (GroupMe's web client
  separately chokes on ~3,000-char pastes — a different limit.)
- Incoming messages include `sender_type` (`"user"` vs `"bot"`) and a
  `system` flag — the code ignores bot, system, and empty messages.
- Polling safety design: claim-before-post (exactly-once), max 3 replies
  per run, outbound posts paced ≥1s apart, corrupt state fails loud
  instead of silently resetting. All proven in `test_poll.py`.

## Phase 1 vs Phase 2

- **Phase 1 (this code):** keyword dispatcher, 4 real skills, runs anywhere
  Python runs. Honest label: role-based skeleton, one brain. Primary
  transport is polling (`poll.py` + cron); the webhook server is the
  low-latency alternative.
- **Phase 2:** swap the dispatcher for LiteLLM/OpenRouter calls so the bot
  understands plain sentences and each skill can run on a *different* model
  (Claude for writing, DeepSeek for code, Kimi for research…). The skills
  don't change — only the dispatcher gets smarter. See the `PHASE 2 NOTE`
  comment at the top of `agent.py`.
