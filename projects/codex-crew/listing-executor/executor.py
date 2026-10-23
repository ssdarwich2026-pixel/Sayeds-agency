"""LISTING EXECUTOR CORE (P4 - C25/C26/C28's modules, one file).

The hands for P1. Takes PACKET READY chunks (same selection rule as
completion-agent/queue.next_chunk - reproduced here to avoid the
stdlib `queue` name shadow) and creates the listings through an
admin driver, then verifies each and writes VERIFIED LIVE back to
P1's ledger with evidence.

Admin driver protocol: any object with
  existing() -> set of (title, print_file) already in the store
  create(packet) -> product id (raises AdminError on failure)
  storefront_titles() -> list of public titles after creation
MockAdmin below is the cage driver; the real Fourthwall CDP driver
plugs into the same protocol on the Pitch lane (single-lane token).

Idempotency, by construction:
- duplicate check by (title, print_file) BEFORE any create: a packet
  whose title or print file is already in the store is BLOCKED in
  the ledger with that reason - never re-created, never deleted.
- crash-resume: only PACKET READY entries are selected, so re-running
  after a crash continues the chunk and cannot double-list (entries
  already advanced are no longer PACKET READY, and the duplicate
  check catches anything the ledger missed).
- single lane: LaneToken must be held for a run; a second holder is
  refused, mirroring the one-Pitch-lane rule.
"""
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "completion-agent"))
from packets import validate_packet  # noqa: E402


class AdminError(Exception):
    pass


class LaneBusy(Exception):
    pass


class LaneToken:
    """Process-local single-lane token (the Pitch lane serialises
    across processes via PITCH-QUEUE.md; this guards in-process)."""

    def __init__(self):
        self._held = False

    def acquire(self):
        if self._held:
            raise LaneBusy("listing lane already held - one lane only")
        self._held = True

    def release(self):
        self._held = False


class MockAdmin:
    """In-memory Fourthwall stand-in for cage tests. fail_on = set of
    print_files whose create() raises AdminError (crash simulation)."""

    def __init__(self, existing=(), storefront_delay=()):
        self.products = {}          # print_file -> packet
        self.titles = {}            # title -> print_file
        for title, pf in existing:
            self.products[pf] = title
            self.titles[title] = pf
        self.fail_on = set()
        self.created = []

    def existing(self):
        return {(t, pf) for pf, t in ((pf, t) for t, pf in self.titles.items())}

    def create(self, packet):
        if packet.print_file in self.fail_on:
            raise AdminError(f"mock admin failure on {packet.print_file}")
        self.products[packet.print_file] = packet.title
        self.titles[packet.title] = packet.print_file
        self.created.append(packet.print_file)
        return f"mock-{len(self.created)}"

    def storefront_titles(self):
        return list(self.titles.keys())


def _ev(source, value):
    return {"source": source, "ts": int(time.time()), "value": value}


class ListingExecutor:
    def __init__(self, ledger, admin, packets_by_key, lane_token,
                 file_exists=lambda p: True):
        self.ledger = ledger
        self.admin = admin
        self.packets_by_key = packets_by_key
        self.lane = lane_token
        self.file_exists = file_exists

    def _next_chunk(self, size):
        chunk = []
        for e in self.ledger.entries.values():
            if e.state == "PACKET READY":
                chunk.append(e.key)
            if len(chunk) == size:
                break
        return chunk

    def run_chunk(self, size=10):
        """One chunk attempt. Returns an honest per-key report; a key
        that fails is BLOCKED in the ledger with the reason, the run
        continues with the rest of the chunk."""
        self.lane.acquire()
        try:
            report = {"created": [], "verified": [], "blocked": [], "refused": []}
            existing = self.admin.existing()
            existing_titles = {t for t, _ in existing}
            existing_files = {pf for _, pf in existing}
            for key in self._next_chunk(size):
                packet = self.packets_by_key.get(key)
                if packet is None:
                    self.ledger.block(key, "no packet supplied for key",
                                       _ev("listing-executor", key))
                    report["blocked"].append((key, "no packet supplied"))
                    continue
                errors = validate_packet(packet, self.file_exists)
                if errors:
                    self.ledger.block(key, "packet invalid: " + "; ".join(errors),
                                       _ev("listing-executor", key))
                    report["refused"].append((key, errors))
                    continue
                if packet.title in existing_titles or packet.print_file in existing_files:
                    self.ledger.block(key, "duplicate: title or print file already in store",
                                       _ev("listing-executor", packet.title))
                    report["blocked"].append((key, "duplicate"))
                    continue
                try:
                    self.admin.create(packet)
                except AdminError as exc:
                    self.ledger.block(key, f"admin create failed: {exc}",
                                       _ev("listing-executor", key))
                    report["blocked"].append((key, str(exc)))
                    continue
                report["created"].append(key)
                self.ledger.transition(key, "LISTED UNVERIFIED",
                                       _ev("listing-executor", packet.title))
                if packet.title in self.admin.storefront_titles():
                    self.ledger.transition(key, "VERIFIED LIVE",
                                           _ev("storefront-verify", packet.title))
                    report["verified"].append(key)
                else:
                    self.ledger.block(key, "created but not visible on storefront",
                                      _ev("storefront-verify", packet.title))
                    report["blocked"].append((key, "not on storefront"))
            return report
        finally:
            self.lane.release()
