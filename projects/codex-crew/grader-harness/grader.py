"""LINE-BY-LINE GRADER (P3 - C18/C19/C20's modules, one file).

Grades customer-facing copy against facts.py. Every historical
Wave 1 failure class is a rule here:
  #360 invented "20% off for the first 100 creators" + limited stock
  #361 "Limited Edition" / scarcity language
  #362 profit leaked into customer copy + wrong duo saving ($32.00)
  #364 invented SHIP10 code, worldwide shipping claim, sizes XS-XXL
Plus: 156-the-target stated as live, duo called a "discount".

grade(text) -> {"verdict": "PASS"|"FAIL", "failures": [...]} where
each failure names the line number, the exact offending quote, and
the rule. Stdlib only.
"""
import re
from decimal import Decimal, InvalidOperation
import facts

RULES = []

def rule(name):
    def deco(fn):
        RULES.append((name, fn))
        return fn
    return deco

@rule("invented-discount")
def _discount(line, low):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*off", low)
    if m:
        return f"percentage discount '{m.group(0)}' - no discounts exist beyond the blitz price"
    return None

@rule("invented-code")
def _code(line, low):
    m = re.search(r"\b(code|promo|coupon)\s*[:\-]?\s*([A-Z0-9]{3,})\b", line)
    if m and m.group(2).upper() not in ("S", "M", "L", "XL"):
        return f"discount/promo code '{m.group(0)}' - no codes exist"
    m2 = re.search(r"\b[A-Z]{3,}\d{1,3}\b", line)
    if m2 and "code" in low:
        return f"discount/promo code '{m2.group(0)}' - no codes exist"
    return None

@rule("scarcity-stock")
def _scarcity(line, low):
    for pat in (r"limited edition", r"limited stock", r"only \d+ left",
                r"while supplies last", r"almost gone", r"low stock",
                r"hurry", r"selling fast", r"stock is limited"):
        m = re.search(pat, low)
        if m:
            return (f"scarcity/stock claim '{m.group(0)}' - print-on-demand, "
                    "no stock limit, no limited editions")
    return None

@rule("profit-leak")
def _profit(line, low):
    for term in facts.INTERNAL_ONLY_TERMS:
        if term in low:
            return f"internal term '{term}' in customer-facing copy - profit figures never ship"
    return None

@rule("target-as-live")
def _target(line, low):
    if "156" in line and re.search(r"\b(live|available now|in stock|on sale now|shop all)\b", low):
        return "'156' stated as live - 156 is the TARGET total, never the live count"
    return None

@rule("duo-called-discount")
def _duo_discount(line, low):
    if "duo" in low and "discount" in low:
        return "the DUO is a bundle price ($29.99 for two), never call it a discount"
    return None

@rule("wrong-savings")
def _savings(line, low):
    for m in re.finditer(r"save\s*\$?\s*(\d+(?:\.\d{2})?)", low):
        try:
            amt = Decimal(m.group(1))
        except InvalidOperation:
            continue
        if amt not in facts.ALLOWED_SAVINGS:
            return (f"saving figure '${m.group(1)}' is wrong - the duo saves "
                    "$9.99 vs buying separately and $41.99 vs compare-at; no other saving exists")
    return None

@rule("wrong-duo-price")
def _duo_price(line, low):
    if "duo" in low:
        for m in re.finditer(r"\$\s*(\d+(?:\.\d{2})?)", line):
            try:
                amt = Decimal(m.group(1))
            except InvalidOperation:
                continue
            allowed = {facts.DUO_PRICE, facts.DUO_SEPARATELY, facts.DUO_COMPARE_AT,
                       facts.DUO_SAVE_SEPARATELY, facts.DUO_SAVE_COMPARE}
            if amt not in allowed:
                return (f"duo line cites '${m.group(1)}' - duo numbers are only "
                        "$29.99 / $39.98 / $71.98 / $9.99 / $41.99")
    return None

@rule("bad-sizes")
def _sizes(line, low):
    for m in re.finditer(r"\b(XS|XXL|6XL|XXXXL|XXS)\b", line):
        return f"size '{m.group(0)}' does not exist - sizes are {facts.SIZE_RANGE_TEXT} only"
    return None

@rule("unverified-shipping")
def _shipping(line, low):
    if "worldwide shipping" in low or "world wide shipping" in low:
        return "'worldwide shipping' claim - shipping answers direct buyers to the store checkout"
    if "free shipping" in low:
        return "'free shipping' claim - not a verified store fact"
    return None

def grade(text):
    failures = []
    for i, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for name, fn in RULES:
            hit = fn(line, low)
            if hit:
                failures.append({"line": i, "quote": line.strip(), "rule": name, "detail": hit})
    return {"verdict": "FAIL" if failures else "PASS", "failures": failures}

if __name__ == "__main__":
    import sys
    result = grade(sys.stdin.read())
    print(result["verdict"])
    for f in result["failures"]:
        print(f"  line {f['line']} [{f['rule']}] {f['detail']} :: {f['quote']}")
    raise SystemExit(0 if result["verdict"] == "PASS" else 1)
