"""Dry-run test: prove the callback logic works with NO GroupMe, NO server.

Run:  python3 test_dryrun.py
Covers the two things that must never break:
  1. The self-reply guard (bot must NEVER answer its own messages).
  2. The four Phase 1 skills end to end against a temp data dir.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
from webhook_logic import chunk_message, parse_command, should_respond


def fake_payload(text, sender_type="user", system=False):
    # Shape of a real GroupMe bot callback (subset of fields we use).
    return {
        "text": text,
        "sender_type": sender_type,
        "system": system,
        "name": "Sayed",
        "group_id": "12345",
    }


checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# --- Self-reply guard & filters -------------------------------------------
check("user message -> reply", should_respond(fake_payload("help")) is True)
check(
    "SELF-REPLY GUARD: bot's own message ignored",
    should_respond(fake_payload("help", sender_type="bot")) is False,
)
check(
    "SELF-REPLY GUARD: bot echo of long text ignored",
    should_respond(fake_payload("x" * 5000, sender_type="bot")) is False,
)
check("system message ignored", should_respond(fake_payload("X joined", system=True)) is False)
check("empty text ignored", should_respond(fake_payload("")) is False)
check("missing text ignored", should_respond({"sender_type": "user"}) is False)
check("garbage payload ignored", should_respond("nope") is False)

# --- Command parsing -------------------------------------------------------
check("parse 'note buy milk'", parse_command("note buy milk") == ("note", "buy milk"))
check("parse tolerates '/help'", parse_command("/help") == ("help", ""))
check("parse tolerates '!STATUS'", parse_command("!STATUS") == ("status", ""))
check("parse empty", parse_command("   ") == ("", ""))

# --- Skills (temp data dir, nothing touches the real one) -------------------
tmp = tempfile.mkdtemp(prefix="bot-test-")
agent = Agent(data_dir=tmp)

r = agent.handle("help", sender_name="Sayed")
check("help lists all skills", all(w in r for w in ("status", "note", "remember", "help")))

r = agent.handle("note NFT prices locked at 0.05 ETH", sender_name="Sayed")
notes = open(os.path.join(tmp, "notes.log")).read()
check("note confirms", "Noted" in r)
check("note persisted with text", "NFT prices locked at 0.05 ETH" in notes)

r = agent.handle("remember Alli is out of town Oct 17 week", sender_name="Sayed")
mem = open(os.path.join(tmp, "memory-scratch.md")).read()
check("remember persists fact", "Alli is out of town Oct 17 week" in mem)

r = agent.handle("status", sender_name="Sayed")
check("status honest when no file yet", "No crew status" in r)
with open(os.path.join(tmp, "crew-status.md"), "w") as f:
    f.write("# Crew status\n- NFT crew: listed 2 foxes on Rarible\n")
r = agent.handle("status", sender_name="Sayed")
check("status reads the file", "listed 2 foxes" in r)

r = agent.handle("frobnicate", sender_name="Sayed")
check("unknown command is friendly", "help" in r.lower())

r = agent.handle("note", sender_name="Sayed")
check("note without text shows usage", "Usage" in r)

# --- Message chunking (bot-posted cap is 1,000 chars, verified) ----------------
long_text = "x" * 6500
chunks = chunk_message(long_text)
check("long reply split into 7 chunks", len(chunks) == 7)
check("every chunk under the limit", all(len(c) <= 990 for c in chunks))
check("chunks reassemble to the original", "".join(chunks) == long_text)
check("short reply not chunked", chunk_message("hi") == ["hi"])

failed = [n for n, c in checks if not c]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
