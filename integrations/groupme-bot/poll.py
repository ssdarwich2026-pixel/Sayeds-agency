"""
Polling transport for the GroupMe bot — the review council's verdict.

POLLING replaces webhook as the primary transport. Instead of a server
waiting for GroupMe to call us (needs a public URL + always-on hosting),
the poller ASKS GroupMe "anything new?" on a schedule (cron, every
5 minutes). $0 on existing workers, no PC, no VPS, no card. Trade:
replies land ~5 minutes after you write, not instantly. The webhook
server (server.py) is kept as the low-latency alternative.

Exactly-once design (read this before "optimizing" it):
  A message is CLAIMED (id recorded in poll-state.json, state saved to
  disk) BEFORE its reply is posted. Consequences:
    - crash after claim, before post  -> a missed reply (rare, silent)
    - crash after post                 -> NO double-reply (id already claimed)
  For a chat bot, a rare missed reply beats a spam loop every time.
  This tradeoff is deliberate and covered by test_poll.py's crash test.

REPLY POLICY NOTE: the first draft of this spec said "answer the NEWEST
qualifying message only". That silently drops every other new message,
which contradicts the exactly-once guarantee the chaos drill verifies
(every message answered exactly once). Implemented instead: answer EVERY
new qualifying message, oldest first, capped at MAX_REPLIES_PER_RUN (3)
replies per run. The cap — not newest-only — is the storm protection.
Flagged to the parent agent; change it back only if dropping messages
becomes the desired behavior.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from webhook_logic import chunk_message, should_respond

MESSAGES_URL = "https://api.groupme.com/v3/groups/{group_id}/messages"
POST_URL = "https://api.groupme.com/v3/bots/post"

FETCH_LIMIT = 100
MAX_REPLIES_PER_RUN = 3
POST_PACE_SECONDS = 1.0
MAX_PROCESSED_IDS = 200  # per group; keeps the state file small
STATE_FILENAME = "poll-state.json"


class HttpError(Exception):
    """An HTTP failure, with status code. status=0 means 'no response at all'."""

    def __init__(self, status, body=""):
        super().__init__("HTTP %s: %s" % (status, str(body)[:200]))
        self.status = status
        self.body = body


def default_http_get(url, headers, params):
    """GET with query params. Injectable so tests never touch the network."""
    qs = urllib.parse.urlencode(params or {})
    req = urllib.request.Request(url + "?" + qs, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.read().decode("utf-8", "replace")[:500])
    except urllib.error.URLError as exc:
        raise HttpError(0, str(exc))


def default_http_post(url, payload):
    """POST a JSON payload. Injectable so tests never touch the network."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 201, 202):
                raise HttpError(resp.status, "unexpected status")
            return {"ok": True}
    except urllib.error.HTTPError as exc:
        raise HttpError(exc.code, exc.read().decode("utf-8", "replace")[:500])
    except urllib.error.URLError as exc:
        raise HttpError(0, str(exc))


def _to_int(value):
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _state_path(data_dir):
    return os.path.join(data_dir, STATE_FILENAME)


def load_state(data_dir):
    """Read poll-state.json. Returns {"groups": {gid: {...}}}.

    A corrupt state file is a LOUD failure, not a silent reset: resetting
    last_seen_id to 0 would re-answer old messages (a reply storm). Cron
    emails the failure; Sayed fixes the file.
    """
    path = _state_path(data_dir)
    if not os.path.exists(path):
        return {"groups": {}}
    with open(path, "r", encoding="utf-8") as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError as exc:
            raise RuntimeError("poll-state.json is corrupt (%s) — fix or delete it" % exc)
    if not isinstance(state, dict) or not isinstance(state.get("groups"), dict):
        raise RuntimeError("poll-state.json has an unexpected shape — fix or delete it")
    return state


def fetch_messages(group_id, after_id, user_token, http_get=default_http_get):
    """Ask GroupMe for messages newer than after_id. Returns a list (maybe empty).

    The user token goes in the X-Access-Token HEADER. Never in the URL —
    URLs end up in logs, caches, and error messages. HTTP 304 means
    "no new messages" and is a normal answer, not an error.
    """
    url = MESSAGES_URL.format(group_id=group_id)
    headers = {"X-Access-Token": user_token}
    params = {"after_id": str(after_id), "limit": str(FETCH_LIMIT)}
    try:
        data = http_get(url, headers=headers, params=params)
    except HttpError as exc:
        if exc.status == 304:
            return []
        raise
    messages = (data.get("response") or {}).get("messages") or []
    return [m for m in messages if isinstance(m, dict)]


class Poller:
    """One poll cycle's worth of logic. Pure-ish: HTTP and sleep are injectable."""

    def __init__(self, user_token, agent, data_dir,
                 http_get=None, http_post=None, sleep_fn=None):
        if not user_token or not str(user_token).strip():
            raise ValueError("user_token is required (GROUPME_USER_TOKEN)")
        self.user_token = str(user_token).strip()
        self.agent = agent
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._http_get = http_get or default_http_get
        self._http_post = http_post or default_http_post
        self._sleep = sleep_fn or time.sleep
        self._posted_before = False  # paces ALL posts >=1s apart, whole poller lifetime

    def _save_group_state(self, state, group_id, last_seen_id, processed):
        trimmed = sorted((str(x) for x in processed), key=lambda s: _to_int(s))
        trimmed = trimmed[-MAX_PROCESSED_IDS:]
        state.setdefault("groups", {})[str(group_id)] = {
            "last_seen_id": str(last_seen_id),
            "processed_ids": trimmed,
        }
        path = _state_path(self.data_dir)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)  # atomic: a crash never leaves a half-written file

    def _post_reply(self, bot_id, text):
        """Post reply text via the bot API, chunked (shared chunker) and paced."""
        for chunk in chunk_message(text):
            if self._posted_before:
                self._sleep(POST_PACE_SECONDS)
            self._http_post(POST_URL, {"bot_id": bot_id, "text": chunk})
            self._posted_before = True

    def poll_group(self, group_id, bot_id, reply_budget=MAX_REPLIES_PER_RUN):
        """One cycle for one group. Returns the number of replies posted.

        Order per message (ascending id): skip seen/claimed -> skip
        non-qualifying (system, bot, empty) -> stop at the reply budget ->
        otherwise CLAIM (persist) then answer. State advances past
        everything handled; unanswered leftovers wait for the next run.
        """
        group_id, bot_id = str(group_id), str(bot_id)
        state = load_state(self.data_dir)
        gstate = state["groups"].get(group_id, {"last_seen_id": "0", "processed_ids": []})
        last_seen = _to_int(gstate.get("last_seen_id", "0"))
        processed = set(str(x) for x in gstate.get("processed_ids", []))

        messages = fetch_messages(group_id, last_seen, self.user_token, self._http_get)
        messages.sort(key=lambda m: _to_int(m.get("id")))  # never trust API ordering

        replies = 0
        advanced = last_seen
        for m in messages:
            mid = _to_int(m.get("id"))
            if mid <= 0:
                continue  # malformed; can't order it, don't advance past it
            if mid <= last_seen or str(mid) in processed:
                advanced = max(advanced, mid)
                continue
            if not should_respond(m):
                advanced = max(advanced, mid)  # seen, never answered
                continue
            if replies >= reply_budget:
                break  # safety fuse; everything from here waits for next run
            # CLAIM (persist) BEFORE posting — see module docstring.
            processed.add(str(mid))
            advanced = max(advanced, mid)
            self._save_group_state(state, group_id, advanced, processed)
            reply = self.agent.handle(
                str(m.get("text") or ""), sender_name=str(m.get("name") or "there")
            )
            if reply:
                self._post_reply(bot_id, reply)
                replies += 1
        self._save_group_state(state, group_id, advanced, processed)
        return replies

    def poll_all(self, groups):
        """Poll every group in {group_id: bot_id}. Returns (replies, errors).

        The reply budget is shared across groups: 3 replies total per run,
        however the groups divide them. A group that errors doesn't stop
        the others; errors are collected for the runner to report.
        """
        total_replies = 0
        errors = {}
        for group_id, bot_id in groups.items():
            try:
                total_replies += self.poll_group(
                    str(group_id), str(bot_id),
                    reply_budget=MAX_REPLIES_PER_RUN - total_replies,
                )
            except Exception as exc:  # one bad group must not sink the run
                errors[str(group_id)] = "%s: %s" % (type(exc).__name__, exc)
        return total_replies, errors
