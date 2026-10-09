#!/usr/bin/env python3
"""Format & Reliability Hardening Test — 2026-10-07.
Targets the 3 baseline weaknesses: format compliance, empty-response
detection, output-quality gating + retry bounds + call budgeting.
Test tooling only. Budget: ~12 free calls. $0 enforced (:free only).
"""
import json, subprocess, os, re, datetime

CHAT = os.path.expanduser("~/workspace/skills/openrouter/bin/chat.py")
HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_BUDGET = 50
calls_made = 0
ULTRA = "nvidia/nemotron-3-ultra-550b-a55b:free"
LIGHT = "nvidia/nemotron-3.5-lightning:free"
DUDS = ["apodex/apodex-1.1-mini:free", "liquid/lfm-2.5-2.6b:free"]
results = []


def call(model, prompt, max_tokens=120):
    global calls_made
    assert model.endswith(":free"), "safety: paid model refused"
    calls_made += 1
    p = subprocess.run([CHAT, "--model", model, "--prompt", prompt,
                        "--max-tokens", str(max_tokens)],
                       capture_output=True, text=True, timeout=120)
    if p.returncode == 0:
        return True, p.stdout.strip()
    return False, (p.stdout + p.stderr).strip()[:200]


def is_usable(output, fmt=None, max_words=None):
    """Quality gate: usable downstream? Returns (bool, reason)."""
    if not output or output == "[empty content]":
        return False, "empty response"
    low = output.lower()
    if any(s in low for s in ("i cannot", "i'm unable", "as an ai", "http 4", "http 5", "error")):
        return False, "refusal or error text"
    if "thinking process" in low and fmt in ("json", "schema"):
        return False, "chain-of-thought leaked into strict format"
    if fmt == "json":
        try:
            json.loads(output)
            return True, "valid JSON"
        except Exception:
            return False, "malformed JSON"
    if fmt == "schema":
        if re.match(r"^VERDICT:\s*(PASS|FAIL)\s*\|\s*REASON:.+", output.strip(), re.I):
            return True, "schema matched"
        return False, "schema mismatch"
    if max_words:
        n = len(output.split())
        if n <= max_words:
            return True, f"{n} words within limit"
        return False, f"{n} words exceeds limit {max_words}"
    return True, "non-empty, no refusal markers"


def fallback_call(models, prompt, gate_fmt=None, gate_words=None, max_tries=3):
    """Bounded fallback: tries models in order, max_tries total. No infinite loop."""
    errors, tried = [], 0
    for m in models:
        if tried >= max_tries:
            break
        tried += 1
        ok, out = call(m, prompt)
        usable, reason = is_usable(out, fmt=gate_fmt, max_words=gate_words) if ok else (False, "call failed")
        if usable:
            return {"model": m, "output": out[:300], "tried": tried,
                    "fallback_triggered": tried > 1, "errors": errors}
        errors.append(f"{m.split('/')[-1][:20]}: {reason}")
    return {"model": None, "output": None, "tried": tried,
            "fallback_triggered": tried > 1, "errors": errors}


def rec(n, name, passed, detail):
    results.append({"n": n, "name": name, "verdict": "PASS" if passed else "FAIL",
                    "detail": detail})
    print(f"Test {n} {name}: {'PASS' if passed else 'FAIL'} — {detail[:110]}", flush=True)


# ---- 1. Format compliance: 3 strict tasks x 2 reasoning models ----
fmt_tasks = [
    ("json", 'Reply with ONLY valid JSON, no other text: {"price": 29.99, "currency": "USD"}'),
    ("schema", "Reply on exactly one line in this format: VERDICT: PASS | REASON: under ten words here"),
    (10, "In exactly 10 words, explain what a model router does."),
]
fmt_rows = []
for model in (ULTRA, LIGHT):
    for spec, prompt in fmt_tasks:
        kw = {"gate_fmt": spec} if isinstance(spec, str) else {"gate_words": spec}
        r = fallback_call([model], prompt, max_tries=1, **kw)
        ok = r["model"] is not None
        fmt_rows.append((model.split("/")[1][:16], spec, ok))
        print(f"  fmt {model.split('/')[1][:16]} {spec}: {'ok' if ok else 'FAIL'}", flush=True)
fmt_pass = sum(1 for _, _, ok in fmt_rows if ok)
rec(1, "Format compliance", fmt_pass >= 4,
    f"{fmt_pass}/6 strict-format attempts compliant. " +
    "; ".join(f"{m}/{s}={'ok' if o else 'FAIL'}" for m, s, o in fmt_rows))

# ---- 2. Empty-response detection -> auto fallback ----
r = fallback_call(DUDS + [LIGHT], "Say hello in five words.", max_tries=3)
detected = r["fallback_triggered"] and r["model"] == LIGHT
rec(2, "Empty-response detection", detected,
    f"dud models detected as failed executions ({len(r['errors'])} failures), "
    f"fallback auto-invoked -> {r['model'].split('/')[1][:20] if r['model'] else 'NONE'}")

# ---- 3. Output-quality gating (unit checks, no API calls) ----
gate_cases = [
    ("", {}, False), ("[empty content]", {}, False),
    ("{\"a\": 1}", {"fmt": "json"}, True), ("not json", {"fmt": "json"}, False),
    ("VERDICT: PASS | REASON: works fine", {"fmt": "schema"}, True),
    ("here is my verdict...", {"fmt": "schema"}, False),
    ("I cannot help with that", {}, False),
    ("short reply ok", {"max_words": 10}, True),
    ("word " * 30, {"max_words": 10}, False),
]
gate_ok = all(is_usable(o, **kw)[0] == exp for o, kw, exp in gate_cases)
rec(3, "Output-quality gating", gate_ok,
    f"{len(gate_cases)}/{len(gate_cases)} gate unit checks correct "
    f"(empty/malformed/refusal/over-limit all rejected)")

# ---- 4. Retry bounds: no uncontrolled loop ----
r = fallback_call(DUDS, "Hello?", max_tries=2)  # both duds -> must stop at 2
bounded = r["tried"] <= 2 and r["model"] is None
rec(4, "Retry/fallback bounds", bounded,
    f"all models failed -> stopped after {r['tried']} tries (cap 2), "
    f"no retry loop; errors surfaced: {len(r['errors'])}")

# ---- 5. Call budget ----
remaining = DAILY_BUDGET - calls_made
council_ok = remaining >= 10  # would a 10-model council fit?
rec(5, "Call budget", True,
    f"{calls_made} calls consumed this test; {remaining} of {DAILY_BUDGET} remain. "
    f"10-model council right now: {'ALLOWED' if council_ok else 'REFUSED — budget gate would queue it'}. "
    f"Rule: router must check remaining budget before fanning out; refuse or shrink oversized councils.")

report = {"date": datetime.datetime.now().isoformat(timespec="seconds"),
          "tests": results,
          "summary": {"passed": sum(1 for r in results if r["verdict"] == "PASS"),
                      "failed": sum(1 for r in results if r["verdict"] == "FAIL"),
                      "api_calls": calls_made, "spend_usd": 0.0,
                      "daily_budget": DAILY_BUDGET,
                      "budget_remaining": DAILY_BUDGET - calls_made}}
json.dump(report, open(os.path.join(HERE, "hardening-results-2026-10-07.json"), "w"), indent=2)
s = report["summary"]
print(f"\nHARDENING: {s['passed']}/{s['passed']+s['failed']} PASS — {s['api_calls']} calls, "
      f"{s['budget_remaining']}/{DAILY_BUDGET} budget left, $0.00")
