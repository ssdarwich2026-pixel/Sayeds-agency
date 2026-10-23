"""STOREFRONT VERIFIER (P1 - completes the verifier TODO).

Compares what the ledger CLAIMS against what an observer SAW on the
storefront. The observed title list is injected by the caller (the
Pitch lane supplies a fresh read); this module does no network I/O,
so it is fully cage-testable and can never hallucinate a storefront.

Drift is named by key, in both directions:
- claimed_not_seen: ledger says VERIFIED LIVE, title not observed.
- seen_not_claimed: title observed live, ledger is not VERIFIED LIVE.
Consistent otherwise. DONE language stays with queue.finish_audit;
this report is the evidence that audit's VERIFIED LIVE states are
backed by an actual storefront read.
"""


def verify_storefront(ledger, observed_titles):
    observed = {t.strip() for t in observed_titles if t and t.strip()}
    claimed_not_seen, seen_not_claimed, confirmed = [], [], []
    title_to_key = {}
    for e in ledger.entries.values():
        title_to_key[e.title] = e.key
        if e.state == "VERIFIED LIVE":
            if e.title in observed:
                confirmed.append(e.key)
            else:
                claimed_not_seen.append(e.key)
    for title in sorted(observed):
        key = title_to_key.get(title)
        if key is None:
            seen_not_claimed.append({"key": None, "title": title})
        elif ledger.entries[key].state != "VERIFIED LIVE":
            seen_not_claimed.append({"key": key, "title": title})
    return {
        "consistent": not claimed_not_seen and not seen_not_claimed,
        "confirmed": sorted(confirmed),
        "claimed_not_seen": sorted(claimed_not_seen),
        "seen_not_claimed": seen_not_claimed,
        "observed_count": len(observed),
    }
