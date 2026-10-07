"""Polling transport tests: the whole cycle with NO GroupMe, NO network.

Run:  python3 test_poll.py
Covers: after_id pagination, 304 handling, self-reply guard,
system-message filter, answer-everything-in-order (cap permitting),
the per-run reply cap, crash-safety (exactly-once), chunking <=1000,
and a chaos drill (missed cycles, every message answered exactly once).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from poll import (
    MAX_REPLIES_PER_RUN,
    HttpError,
    Poller,
    fetch_messages,
    load_state,
)


def msg(mid, text, sender_type="user", system=False, name="Sayed"):
    # Shape of one entry in GroupMe's messages index (subset we use).
    return {
        "id": str(mid),
        "text": text,
        "sender_type": sender_type,
        "system": system,
        "name": name,
        "group_id": "g1",
    }


class CrashSimulated(Exception):
    pass


class FakeGroupMe:
    """In-memory GroupMe: messages index + bot post endpoint."""

    def __init__(self):
        self.messages = {}  # group_id -> [message dicts]
        self.posts = []  # every posted payload, in order
        self.get_calls = []  # (url, headers, params) for assertions
        self.sleeps = []  # sleep durations, in order
        self.fail_get_with = None  # set to HttpError(...) to simulate
        self.crash_after_posts = None  # raise CrashSimulated after N posts

    # -- transport ------------------------------------------------------
    def http_get(self, url, headers, params):
        assert headers.get("X-Access-Token") == "tok-user", "token must ride the header"
        assert "tok-user" not in url, "token must NEVER appear in the URL"
        self.get_calls.append((url, dict(headers), dict(params)))
        if self.fail_get_with is not None:
            raise self.fail_get_with
        gid = url.rstrip("/").split("/")[-2]  # .../groups/<gid>/messages
        after = int(params.get("after_id", 0))
        msgs = [m for m in self.messages.get(gid, []) if int(m["id"]) > after]
        return {"response": {"messages": msgs, "count": len(msgs)}}

    def http_post(self, url, payload):
        assert url.endswith("/bots/post")
        self.posts.append(dict(payload))
        if self.crash_after_posts is not None and len(self.posts) >= self.crash_after_posts:
            raise CrashSimulated("boom: died right after posting")
        return {"ok": True}

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    # -- helpers ---------------------------------------------------------
    def add(self, group_id, *messages):
        self.messages.setdefault(group_id, []).extend(messages)

    def poller(self, agent=None, tmp=None):
        tmp = tmp or tempfile.mkdtemp(prefix="poll-test-")
        return Poller(
            user_token="tok-user",
            agent=agent if agent is not None else SilentAgent(),
            data_dir=tmp,
            http_get=self.http_get,
            http_post=self.http_post,
            sleep_fn=self.sleep,
        ), tmp


class SilentAgent:
    """Answers every command with a fixed short reply (for transport tests)."""

    def __init__(self, reply="ok"):
        self.reply = reply
        self.seen = []

    def handle(self, text, sender_name="there"):
        self.seen.append(text)
        return self.reply


class LongAgent:
    def handle(self, text, sender_name="there"):
        return "y" * 2500


checks = []


def check(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# --- 1. after_id pagination + state advancement ---------------------------
fake = FakeGroupMe()
fake.add("g1", msg(10, "note one"), msg(20, "note two"))
poller, tmp = fake.poller()
check("two new messages -> 2 replies", poller.poll_group("g1", "bot1") == 2)
state = load_state(tmp)
check("state advanced to newest id", state["groups"]["g1"]["last_seen_id"] == "20")
check("after_id=0 used on first fetch", fake.get_calls[0][2]["after_id"] == "0")
check("second run sees nothing new", poller.poll_group("g1", "bot1") == 0)
check("after_id=20 used on second fetch", fake.get_calls[1][2]["after_id"] == "20")

# --- 2. HTTP 304 = "no new messages", not an error -------------------------
fake = FakeGroupMe()
fake.fail_get_with = HttpError(304, "")
poller, tmp = fake.poller()
check("304 -> 0 replies, no exception", poller.poll_group("g1", "bot1") == 0)

# --- 3. self-reply guard ----------------------------------------------------
fake = FakeGroupMe()
fake.add("g1", msg(11, "note hi", sender_type="bot"), msg(12, "note hi"))
poller, tmp = fake.poller()
check("bot's own message never answered", poller.poll_group("g1", "bot1") == 1)
check("only the user message was posted for",
      len(fake.posts) == 1)
state = load_state(tmp)
check("state advanced past the bot message too",
      state["groups"]["g1"]["last_seen_id"] == "12")

# --- 4. system-message filter -------------------------------------------------
fake = FakeGroupMe()
fake.add("g1", msg(13, "Ava joined the group", system=True), msg(14, "status"))
poller, tmp = fake.poller()
check("system message skipped, user message answered",
      poller.poll_group("g1", "bot1") == 1)
state = load_state(tmp)
check("state advanced past the system message",
      state["groups"]["g1"]["last_seen_id"] == "14")

# --- 5. every new message answered, oldest first (cap permitting) ------------
fake = FakeGroupMe()
agent = SilentAgent()
fake.add("g1", msg(21, "note a"), msg(22, "note b"), msg(23, "note c"))
poller, tmp = fake.poller(agent=agent)
check("3 new messages -> 3 replies", poller.poll_group("g1", "bot1") == 3)
check("answered oldest-first", agent.seen == ["note a", "note b", "note c"])

# --- 6. per-run reply cap: leftovers wait for the next run --------------------
fake = FakeGroupMe()
agent = SilentAgent()
fake.add("g1", *[msg(30 + i, "note %d" % i) for i in range(5)])
poller, tmp = fake.poller(agent=agent)
check("cap is 3", MAX_REPLIES_PER_RUN == 3)
check("first run posts exactly 3", poller.poll_group("g1", "bot1") == 3)
check("second run posts the remaining 2", poller.poll_group("g1", "bot1") == 2)
check("all 5 answered exactly once", len(fake.posts) == 5)
texts = [p["text"] for p in fake.posts]
check("no duplicate replies", len(set(texts)) == 1 and len(texts) == 5)  # same reply text...
# ...so verify exactly-once via the agent's seen list instead:
check("agent saw each message exactly once",
      sorted(agent.seen) == sorted("note %d" % i for i in range(5)))
state = load_state(tmp)
check("state advanced to the last id", state["groups"]["g1"]["last_seen_id"] == "34")

# --- 7. crash AFTER reply, BEFORE run ends -> NO double-reply -----------------
fake = FakeGroupMe()
fake.add("g1", msg(40, "note survive the crash"))
poller, tmp = fake.poller()
fake.crash_after_posts = 1
crashed = False
try:
    poller.poll_group("g1", "bot1")
except CrashSimulated:
    crashed = True
check("crash was simulated", crashed)
check("the reply WAS posted before the crash", len(fake.posts) == 1)
fake.crash_after_posts = None  # process "restarts"
# point the new poller at the SAME state dir to simulate the restart
poller2 = Poller(user_token="tok-user", agent=SilentAgent(), data_dir=tmp,
                 http_get=fake.http_get, http_post=fake.http_post, sleep_fn=fake.sleep)
check("restart: message NOT answered again", poller2.poll_group("g1", "bot1") == 0)
check("exactly one post total (no double-reply)", len(fake.posts) == 1)

# --- 8. chunking: long replies stay <=1000 chars -------------------------------
fake = FakeGroupMe()
fake.add("g1", msg(50, "status"))
poller, tmp = fake.poller(agent=LongAgent())
check("long reply posted", poller.poll_group("g1", "bot1") == 1)
check("2500 chars -> 3 chunks", len(fake.posts) == 3)
check("every chunk <= 1000 chars", all(len(p["text"]) <= 1000 for p in fake.posts))
check("chunks reassemble", "".join(p["text"] for p in fake.posts) == "y" * 2500)

# --- 9. chaos drill: 2 missed cycles, messages in between ----------------------
fake = FakeGroupMe()
agent = SilentAgent()
poller, tmp = fake.poller(agent=agent)
# missed cycle 1: one message arrives, nobody polls
fake.add("g1", msg(101, "note alpha"))
# missed cycle 2: two more arrive (plus a system message)
fake.add("g1", msg(102, "note beta"), msg(103, "remember gamma"),
         msg(104, "Ava joined", system=True))
# recovery run
check("recovery run answers the 3 user messages",
      poller.poll_group("g1", "bot1") == 3)
check("every message answered exactly once",
      sorted(agent.seen) == ["note alpha", "note beta", "remember gamma"])
check("no duplicate posts", len(fake.posts) == 3)
state = load_state(tmp)
check("state advanced past everything, incl. the system message",
      state["groups"]["g1"]["last_seen_id"] == "104")
check("processed ids persisted", len(state["groups"]["g1"]["processed_ids"]) == 3)
check("next run is quiet", poller.poll_group("g1", "bot1") == 0)
# pacing: 3 single-chunk posts -> 2 sleeps of >=1s between them
check("outbound posts paced >=1s apart",
      fake.sleeps == [1.0, 1.0])

# --- 10. corrupt state file fails LOUD (never silently resets) -----------------
tmp = tempfile.mkdtemp(prefix="poll-test-")
with open(os.path.join(tmp, "poll-state.json"), "w") as f:
    f.write("{not json")
fake = FakeGroupMe()
poller, _ = fake.poller(tmp=tmp)
loud = False
try:
    poller.poll_group("g1", "bot1")
except RuntimeError:
    loud = True
check("corrupt state -> loud failure, no silent reset", loud)

# --- 11. token rides the header, never the URL (paranoia check) -----------------
fake = FakeGroupMe()
poller, tmp = fake.poller()
poller.poll_group("g1", "bot1")
_, headers, _ = fake.get_calls[0]
check("X-Access-Token header present", headers.get("X-Access-Token") == "tok-user")

# --- 12. first-run catch-up: old chatter gets no reply, commands still work --
from agent import is_known_command
check("is_known_command: 'help' -> True", is_known_command("help") is True)
check("is_known_command: 'Help me' -> True", is_known_command("Help me") is True)
check("is_known_command: '!status' -> True", is_known_command("!status") is True)
check("is_known_command: emoji chatter -> False",
      is_known_command("\u26a1 some old chatter") is False)
check("is_known_command: empty -> False", is_known_command("") is False)
fake = FakeGroupMe()
fake.add("g1", msg(201, "\u26a1 some old chatter"),
         msg(202, "help"),
         msg(203, "just talking here"))
agent = SilentAgent()
poller, tmp = fake.poller(agent=agent)
check("first run answers only the known command",
      poller.poll_group("g1", "bot1") == 1)
check("only 'help' was handed to the agent", agent.seen == ["help"])
check("exactly one post", len(fake.posts) == 1)
state = load_state(tmp)
check("state advanced past the chatter too",
      state["groups"]["g1"]["last_seen_id"] == "203")
check("all three marked processed",
      len(state["groups"]["g1"]["processed_ids"]) == 3)
check("second run is quiet", poller.poll_group("g1", "bot1") == 0)

# --- 13. catch-up applies per group, not globally -----------------------------
fake = FakeGroupMe()
fake.add("g1", msg(301, "old chatter"))
fake.add("g2", msg(302, "old chatter"))
poller, tmp = fake.poller()
check("g1 first run: chatter skipped", poller.poll_group("g1", "bot1") == 0)
check("g2 first run: chatter skipped too", poller.poll_group("g2", "bot2") == 0)
fake.add("g1", msg(303, "status"))
check("g1 second run: real command answered",
      poller.poll_group("g1", "bot1") == 1)

failed = [n for n, c in checks if not c]
print("\n%d/%d checks passed" % (len(checks) - len(failed), len(checks)))
sys.exit(1 if failed else 0)
