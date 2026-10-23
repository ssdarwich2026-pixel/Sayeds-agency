"""LEDGER STATE MACHINE (P1 - C01's module).

One state per design, changed only on evidence:
  NOT STARTED -> PACKET READY -> LISTED UNVERIFIED -> VERIFIED LIVE
  any state -> BLOCKED (reason named); BLOCKED -> its prior state on
  clearing evidence. Evidence = {source, ts, value} - a state change
  without evidence raises. No vibes, no fourth-hand summaries.
"""
import time

STATES = ("NOT STARTED", "PACKET READY", "LISTED UNVERIFIED", "VERIFIED LIVE", "BLOCKED")
FLOW = {"NOT STARTED": {"PACKET READY"},
        "PACKET READY": {"LISTED UNVERIFIED"},
        "LISTED UNVERIFIED": {"VERIFIED LIVE", "PACKET READY"},
        "VERIFIED LIVE": set(),
        "BLOCKED": set()}  # exit handled via unblock()

class LedgerError(Exception):
    pass

class Entry:
    def __init__(self, key, title, print_file):
        self.key, self.title, self.print_file = key, title, print_file
        self.state = "NOT STARTED"
        self.blocked_reason = None
        self._pre_block_state = None
        self.history = []

class Ledger:
    def __init__(self):
        self.entries = {}

    def add(self, key, title, print_file):
        if key in self.entries:
            raise LedgerError(f"duplicate entry {key}")
        self.entries[key] = Entry(key, title, print_file)
        return self.entries[key]

    @staticmethod
    def _check_evidence(evidence):
        if not evidence or not all(k in evidence for k in ("source", "ts", "value")):
            raise LedgerError("state changes require evidence {source, ts, value}")

    def transition(self, key, new_state, evidence):
        self._check_evidence(evidence)
        e = self.entries[key]
        if e.state == "BLOCKED":
            raise LedgerError(f"{key} is BLOCKED ({e.blocked_reason}); unblock first")
        if new_state not in FLOW[e.state]:
            raise LedgerError(f"illegal transition {e.state} -> {new_state} for {key}")
        e.state = new_state
        e.history.append({"to": new_state, "evidence": evidence, "at": int(time.time())})
        return e

    def block(self, key, reason, evidence):
        self._check_evidence(evidence)
        e = self.entries[key]
        if e.state == "BLOCKED":
            raise LedgerError(f"{key} already BLOCKED")
        e._pre_block_state = e.state
        e.state, e.blocked_reason = "BLOCKED", reason
        e.history.append({"to": "BLOCKED", "reason": reason, "evidence": evidence, "at": int(time.time())})
        return e

    def unblock(self, key, evidence):
        self._check_evidence(evidence)
        e = self.entries[key]
        if e.state != "BLOCKED":
            raise LedgerError(f"{key} is not BLOCKED")
        e.state, e.blocked_reason = e._pre_block_state, None
        e.history.append({"to": e.state, "unblocked": True, "evidence": evidence, "at": int(time.time())})
        return e

    def counts(self):
        out = {s: 0 for s in STATES}
        for e in self.entries.values():
            out[e.state] += 1
        out["total"] = len(self.entries)
        return out

    def remaining(self):
        return [e.key for e in self.entries.values() if e.state != "VERIFIED LIVE"]
