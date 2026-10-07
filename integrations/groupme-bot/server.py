"""
GroupMe bot webhook server — the "office intercom".

Run it with:  ./run.sh
(Or manually:  uvicorn server:app --host 0.0.0.0 --port 8000)

How it works:
  1. GroupMe POSTs to /webhook/<secret> every time someone writes in a
     group where the bot lives.
  2. We check the secret, then ask: is this worth replying to?
     (Never reply to the bot's own messages — see webhook_logic.)
  3. The agent loop produces a reply.
  4. We post the reply back through GroupMe's official bot API.

Security note: GroupMe does NOT sign its bot callbacks, so there is no
signature to verify. Instead the secret lives in the URL path itself —
https://your-host/webhook/<long-random-secret> — and anything without
the exact secret gets a 403. Keep that URL private, like a password.
"""

import json
import logging
import os
import urllib.error
import urllib.request

# Optional: load a .env file if python-dotenv is installed. Plain
# environment variables always work too.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException, Request

from agent import Agent
from webhook_logic import chunk_message, should_respond

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("groupme-bot")

BOT_ID = os.environ.get("GROUPME_BOT_ID", "").strip()
CALLBACK_SECRET = os.environ.get("CALLBACK_SECRET", "").strip()

# Fail fast on bad config — a bot that can't post or can't verify its
# webhook should never start silently.
if not BOT_ID:
    raise RuntimeError("GROUPME_BOT_ID is not set. Copy it from https://dev.groupme.com/bots")
if not CALLBACK_SECRET:
    raise RuntimeError("CALLBACK_SECRET is not set. Pick a long random string and keep it private.")

GROUPME_POST_URL = "https://api.groupme.com/v3/bots/post"

agent = Agent()
app = FastAPI(title="Agency GroupMe Bot")


def post_to_groupme(text: str) -> None:
    """Post reply text back to the group via the official bot API.

    Posting needs only the bot_id — no auth token. Long replies are
    chunked so no single message trips GroupMe's length limit.
    """
    for chunk in chunk_message(text):
        payload = json.dumps({"bot_id": BOT_ID, "text": chunk}).encode("utf-8")
        req = urllib.request.Request(
            GROUPME_POST_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status not in (200, 201, 202):
                    log.error("GroupMe post returned HTTP %s", resp.status)
        except urllib.error.URLError as exc:
            # Log the failure, don't crash the webhook — GroupMe will retry.
            log.error("GroupMe post failed: %s", exc)


@app.post("/webhook/{secret}")
async def webhook(secret: str, request: Request):
    if secret != CALLBACK_SECRET:
        raise HTTPException(status_code=403, detail="bad secret")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="expected JSON")
    if not should_respond(payload):
        return {"ok": True, "replied": False}
    sender = str(payload.get("name") or "there")
    # Never log message text at INFO — groups can contain private chatter.
    log.info("Message from %s in group %s", sender, payload.get("group_id"))
    reply = agent.handle(str(payload.get("text") or ""), sender_name=sender)
    if reply:
        post_to_groupme(reply)
        return {"ok": True, "replied": True}
    return {"ok": True, "replied": False}


@app.get("/healthz")
async def healthz():
    return {"ok": True, "bot_configured": bool(BOT_ID)}


@app.get("/")
async def index():
    return {
        "ok": True,
        "service": "Sayed's Agency GroupMe Bot",
        "usage": "POST GroupMe callbacks to /webhook/<secret>",
    }
