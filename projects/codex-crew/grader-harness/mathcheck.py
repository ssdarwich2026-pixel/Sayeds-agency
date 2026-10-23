"""MATHCHECK (P3 - the pricing-proof module named in C20's graduation set).

Verifies the store's money numbers are internally consistent, reading
only facts.py (the single verified-facts source). Run as part of the
P3 suite so a facts.py typo breaks the build before it breaks a
grader rule. verify_savings_claim lets callers (and future P14) check
a "save $X" claim against the allowed savings without touching floats.
"""
from decimal import Decimal

import facts


def _ok(name, cond, detail=""):
    return {"name": name, "pass": bool(cond), "detail": detail}


def run_checks():
    checks = [
        _ok("duo-separately-is-2x-single",
            facts.DUO_SEPARATELY == facts.SINGLE_PRICE * 2,
            f"{facts.DUO_SEPARATELY} vs 2 x {facts.SINGLE_PRICE}"),
        _ok("save-vs-separately",
            facts.DUO_SEPARATELY - facts.DUO_PRICE == facts.DUO_SAVE_SEPARATELY,
            f"{facts.DUO_SEPARATELY} - {facts.DUO_PRICE}"),
        _ok("save-vs-compare-at",
            facts.DUO_COMPARE_AT - facts.DUO_PRICE == facts.DUO_SAVE_COMPARE,
            f"{facts.DUO_COMPARE_AT} - {facts.DUO_PRICE}"),
        _ok("allowed-savings-match",
            facts.ALLOWED_SAVINGS == {facts.DUO_SAVE_SEPARATELY, facts.DUO_SAVE_COMPARE},
            str(sorted(facts.ALLOWED_SAVINGS))),
        _ok("sizes-include-s-through-5xl",
            facts.SIZES[:5] == ["S", "M", "L", "XL", "2XL"] and "5XL" in facts.SIZES,
            facts.SIZE_RANGE_TEXT),
        _ok("internal-terms-nonempty",
            len(facts.INTERNAL_ONLY_TERMS) > 0, "profit leak list populated"),
    ]
    return checks


def verify_savings_claim(amount):
    """True when amount is one of the two verified savings figures."""
    try:
        return Decimal(str(amount)) in facts.ALLOWED_SAVINGS
    except Exception:
        return False


def all_pass():
    return all(c["pass"] for c in run_checks())


if __name__ == "__main__":
    checks = run_checks()
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["name"] + " :: " + c["detail"])
    raise SystemExit(0 if all_pass() else 1)
