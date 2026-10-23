"""CHUNK QUEUE + FINISH AUDIT (P1 - C04/C05's modules).

The queue hands the single listing lane the next chunk of 10
PACKET READY designs in ledger (manifest) order. This agent
composes and lists NOTHING itself.
Finish audit: DONE only when every entry is VERIFIED LIVE and the
remaining list is empty - otherwise the exact remaining keys.
"""
from ledger import Ledger

def next_chunk(ledger: Ledger, size: int = 10):
    chunk = []
    for e in ledger.entries.values():
        if e.state == "PACKET READY":
            chunk.append(e.key)
        if len(chunk) == size:
            break
    return chunk

def finish_audit(ledger: Ledger, target: int):
    counts = ledger.counts()
    remaining = ledger.remaining()
    done = (counts["VERIFIED LIVE"] == target and not remaining
            and counts["total"] == target)
    return {"done": done, "verified_live": counts["VERIFIED LIVE"],
            "target": target, "remaining": remaining,
            "blocked": [e.key for e in ledger.entries.values() if e.state == "BLOCKED"]}
