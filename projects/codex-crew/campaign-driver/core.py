"""CAMPAIGNDRIVER CORE (P2 - C09/C10/C11/C13's modules, one file).

Handshake rule, in code: this agent promotes ONLY designs whose
P1 ledger state is VERIFIED LIVE. PACKET READY is never promoted.
Every payload passes the P3 grader before it may queue; a FAIL
blocks with the grader's exact failures attached.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "grader-harness"))
import grader  # noqa: E402

FEATURED_ORDER = ["53 SANS-BEGAYER", "54 BLUE-SCARF", "DUO"]
PLATFORMS = ["instagram-1", "instagram-2", "tiktok", "facebook", "threads", "youtube-shorts"]
STORE_LINK = "https://shiptrollyard-shop.fourthwall.com"

class Blocked(Exception):
    def __init__(self, failures):
        super().__init__("payload blocked by grader")
        self.failures = failures

class CampaignDriver:
    def __init__(self, ledger_states):
        # ledger_states: {design_key: state} from P1's ledger
        self.ledger_states = dict(ledger_states)
        self.queue = []

    def promote(self, design_key, copy_text):
        state = self.ledger_states.get(design_key)
        if state != "VERIFIED LIVE":
            raise Blocked([{"rule": "not-verified-live", "quote": design_key,
                            "detail": f"state is {state!r}; only VERIFIED LIVE may be promoted"}])
        result = grader.grade(copy_text)
        if result["verdict"] == "FAIL":
            raise Blocked(result["failures"])
        payload = {"design": design_key, "copy": copy_text, "link": STORE_LINK}
        self.queue.append(payload)
        return payload

    def featured_first(self, keys):
        rank = {name: i for i, name in enumerate(FEATURED_ORDER)}
        return sorted(keys, key=lambda k: (rank.get(k, 99), k))

    def build_day(self):
        """One payload per platform, featured order first."""
        keys = self.featured_first([p["design"] for p in self.queue])
        by_design = {p["design"]: p for p in self.queue}
        day = []
        for i, platform in enumerate(PLATFORMS):
            if not keys:
                break
            design = keys[i % len(keys)]
            day.append({"platform": platform, **by_design[design]})
        return day
