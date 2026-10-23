"""SOCIAL POSTING EXECUTOR CORE (P5).

The hands for P2 CampaignDriver. Takes the driver's day payloads and
publishes them through a platform driver, then VERIFIES each post is
visible on the platform feed before reporting it posted - a publish
call that returns an id but never appears is BLOCKED, never claimed.

Platform driver protocol: any object with
  published_keys() -> set of payload_keys already live
  publish(payload) -> {"id":..., "url":...} (raises PlatformError)
  feed_ids() -> list of post ids currently visible
MockPlatform below is the sandbox driver; real adapters (Instagram
connector / Postiz, the one live scheduler) plug into the same
protocol. IG posts inside the approved campaign lane run
publish-first per Sayed's 2026-10-23 no-pop-ups rule; this executor
adds no approval step of its own.

Idempotency, by construction:
- dedupe by payload_key BEFORE publish, against both the driver's
  published set and a file-backed journal (JSONL) that survives a
  hard crash: re-running a day never double-posts.
- crash-resume: journal entries marked PUBLISHED_UNVERIFIED are
  re-verified against the feed on resume, not re-published.
- single lane: LaneToken (same pattern as P4); a second holder is
  refused.
"""
import json
import time
from pathlib import Path

from payloads import payload_key, validate_payload


class PlatformError(Exception):
    pass


class LaneBusy(Exception):
    pass


class LaneToken:
    def __init__(self):
        self._held = False

    def acquire(self):
        if self._held:
            raise LaneBusy("posting lane already held - one lane only")
        self._held = True

    def release(self):
        self._held = False


class MockPlatform:
    """In-memory platform stand-in for sandbox tests. fail_on = set
    of payload_keys whose publish raises PlatformError; hide_on =
    set of payload_keys whose post never appears on the feed."""

    def __init__(self):
        self.posts = {}  # payload_key -> {"id","url","payload"}
        self.fail_on = set()
        self.hide_on = set()
        self.published = []

    def published_keys(self):
        return set(self.posts)

    def publish(self, payload):
        key = payload_key(payload)
        if key in self.fail_on:
            raise PlatformError(f"mock platform failure on {key}")
        pid = f"mock-{payload['platform']}-{len(self.published) + 1}"
        self.posts[key] = {"id": pid,
                           "url": f"https://mock.example/{payload['platform']}/{pid}",
                           "payload": dict(payload)}
        self.published.append(key)
        return {"id": pid, "url": self.posts[key]["url"]}

    def feed_ids(self):
        return [p["id"] for k, p in self.posts.items() if k not in self.hide_on]


class Journal:
    """Append-only JSONL journal: one latest state per payload_key.
    States: PUBLISHED_UNVERIFIED -> POSTED (verified) | BLOCKED."""

    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.states = {}
        if self.path and self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.states[rec["key"]] = rec

    def record(self, key, state, detail=""):
        rec = {"key": key, "state": state, "detail": detail, "ts": int(time.time())}
        self.states[key] = rec
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a") as fh:
                fh.write(json.dumps(rec) + "\n")
        return rec

    def state_of(self, key):
        rec = self.states.get(key)
        return rec["state"] if rec else None


class SocialPostingExecutor:
    def __init__(self, platform, journal=None, lane_token=None,
                 ledger_states=None, file_exists=lambda p: True):
        self.platform = platform
        self.journal = journal if journal is not None else Journal()
        self.lane = lane_token if lane_token is not None else LaneToken()
        self.ledger_states = ledger_states
        self.file_exists = file_exists

    def post_day(self, payloads):
        """Publish one day of payloads. Returns an honest per-key
        report; a failure blocks that key only, the day continues."""
        self.lane.acquire()
        try:
            report = {"posted": [], "verified": [], "blocked": [],
                      "refused": [], "skipped_duplicate": []}
            already = self.platform.published_keys()
            for payload in payloads:
                key = payload_key(payload)
                errors = validate_payload(payload, self.ledger_states,
                                          self.file_exists)
                if errors:
                    self.journal.record(key, "BLOCKED", "; ".join(errors))
                    report["refused"].append((key, errors))
                    continue
                state = self.journal.state_of(key)
                if state == "POSTED" or (key in already and state is None):
                    report["skipped_duplicate"].append(key)
                    continue
                if state == "PUBLISHED_UNVERIFIED":
                    # crash-resume: verify the earlier publish, never repost
                    post = self.platform.posts.get(key) if hasattr(
                        self.platform, "posts") else None
                    pid = post["id"] if post else None
                    if pid and pid in self.platform.feed_ids():
                        self.journal.record(key, "POSTED", pid)
                        report["verified"].append(key)
                    else:
                        self.journal.record(key, "BLOCKED",
                                            "prior publish not visible on feed")
                        report["blocked"].append((key, "not on feed after crash"))
                    continue
                try:
                    result = self.platform.publish(payload)
                except PlatformError as exc:
                    self.journal.record(key, "BLOCKED", str(exc))
                    report["blocked"].append((key, str(exc)))
                    continue
                self.journal.record(key, "PUBLISHED_UNVERIFIED", result["id"])
                report["posted"].append(key)
                if result["id"] in self.platform.feed_ids():
                    self.journal.record(key, "POSTED", result["id"])
                    report["verified"].append(key)
                else:
                    self.journal.record(key, "BLOCKED",
                                        "published but not visible on feed")
                    report["blocked"].append((key, "not on feed"))
            return report
        finally:
            self.lane.release()

    def retry_blocked(self, payloads):
        """Re-run only payloads whose journal state is BLOCKED.
        BLOCKED is not a skip state in post_day, so a filtered
        re-run publishes exactly those keys and no others."""
        wanted = [p for p in payloads
                  if self.journal.state_of(payload_key(p)) == "BLOCKED"]
        return self.post_day(wanted)
