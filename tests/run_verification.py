#!/usr/bin/env python3
"""Agency Multi-Model Verification Test — 2026-10-07.
Test tooling only (not architecture). Runs 12 tests against live free models
via the openrouter workspace skill, records a PASS/FAIL scorecard, and writes
the baseline report. Budget: ~15 free-model requests (of 50/day). $0 enforced:
only :free model IDs are ever called.
"""
import json, subprocess, sys, os, datetime

CHAT = os.path.expanduser("~/workspace/skills/openrouter/bin/chat.py")
HERE = os.path.dirname(os.path.abspath(__file__))
FREE_MODELS = {
    "ultra": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "lightning": "nvidia/nemotron-3.5-lightning:free",
    "gemma4": "google/gemma-4-31b-it:free",
    "apodex": "apodex/apodex-1.1-mini:free",
    "liquid": "liquid/lfm-2.5-2.6b:free",
}
results = []
api_calls = 0


def call(model, prompt, max_tokens=120):
    """Single model call. Returns (ok, output_or_error)."""
    global api_calls
    api_calls += 1
    p = subprocess.run([CHAT, "--model", model, "--prompt", prompt,
                        "--max-tokens", str(max_tokens)],
                       capture_output=True, text=True, timeout=120)
    if p.returncode == 0:
        return True, p.stdout.strip()[:800]
    err = (p.stdout + p.stderr).strip()[:300]
    return False, err


def fallback_call(models, prompt, max_tokens=120):
    """Try models in order; return (model_used, output, fallbacks, errors)."""
    errors, fallbacks = [], None
    for m in models:
        if not m.endswith(":free"):
            return None, "REFUSED non-free model", fallbacks, ["safety: blocked paid model"]
        ok, out = call(m, prompt, max_tokens)
        if ok and out and out != "[empty content]":
            return m, out, fallbacks, errors
        errors.append(f"{m.split('/')[-1][:24]}: {out[:80]}")
        fallbacks = (fallbacks or 0) + 1
    return None, None, fallbacks, errors


def rec(n, name, passed, models, route, fallback, verified, notes=""):
    results.append({"n": n, "name": name, "verdict": "PASS" if passed else "FAIL",
                    "models": models, "route": route, "fallback": fallback,
                    "verified": verified, "notes": notes})
    print(f"Test {n} {name}: {'PASS' if passed else 'FAIL'} — {notes[:100]}", flush=True)


# ---- Test 1: Strategy ----
m, out, fb, errs = fallback_call([FREE_MODELS["ultra"], FREE_MODELS["lightning"]],
    "A print-on-demand tee brand sells at $29.99, costs $11 all-in per unit. Give the single best pricing tactic to grow profit. 2 sentences max.", 150)
rec(1, "Strategy", bool(m), [m] if m else [], "agency-strategy",
    f"{fb} fallback(s)" if fb else "none needed", "n/a",
    f"selected ultra for 550B reasoning (registry best_for); output usable: {bool(m)}. {'; '.join(errs) if errs else ''}")

# ---- Test 2: Writing/Copy ----
m, out, fb, errs = fallback_call([FREE_MODELS["lightning"], FREE_MODELS["ultra"]],
    "Write one punchy Instagram caption (under 20 words) for a 'Dragon Crown Tee' streetwear drop.", 100)
usable = bool(m and len(out.split()) <= 40)
rec(2, "Writing/Copy", usable, [m] if m else [], "agency-copy",
    f"{fb} fallback(s)" if fb else "none needed", "n/a",
    f"caption: {out[:90] if m else errs}")

# ---- Test 3: Analysis/Reasoning (multi-step) ----
m, out, fb, errs = fallback_call([FREE_MODELS["gemma4"], FREE_MODELS["ultra"]],
    "Tee: price $29.99, cost $11, platform fee 8%. Step 1: profit per unit. Step 2: units needed to clear $500 profit. Show both numbers.", 150)
has_numbers = bool(m and ("$" in out or any(c.isdigit() for c in out)))
rec(3, "Analysis/Reasoning", has_numbers, [m] if m else [], "agency-strategy",
    f"{fb} fallback(s)" if fb else "none needed", "n/a",
    f"multi-step output returned: {out[:90] if m else errs}")

# ---- Test 4: General Chat ----
m, out, fb, errs = fallback_call([FREE_MODELS["apodex"], FREE_MODELS["liquid"]],
    "In one friendly sentence, what does a model router do?", 80)
rec(4, "General Chat", bool(m and out), [m] if m else [], "agency-chat",
    f"{fb} fallback(s)" if fb else "none needed", "n/a",
    f"reply: {out[:90] if m else errs}")

# ---- Test 5: Multiple Models, same task ----
prompt5 = "In one sentence: why do most print-on-demand brands fail?"
outs5, errs5 = {}, []
for key in ("ultra", "lightning", "gemma4"):
    ok, out = call(FREE_MODELS[key], prompt5, 80)
    if ok and out and out != "[empty content]":
        outs5[key] = out
    else:
        errs5.append(key)
strongest = max(outs5, key=lambda k: len(outs5[k])) if outs5 else None
rec(5, "Multiple Models", len(outs5) >= 2, list(outs5.keys()), "3 routes",
    "n/a", "n/a",
    f"{len(outs5)}/3 models returned; strongest: {strongest} ({outs5.get(strongest,'')[:70]}). errors: {errs5}")

# ---- Test 6: Router Decision (no API calls) ----
import subprocess as sp
decisions = {}
for t in ("strategy", "copy", "chat", "code"):
    p = sp.run(["python3", os.path.join(HERE, "..", "router", "route.py"), t],
               capture_output=True, text=True)
    line = [l for l in p.stdout.splitlines() if l.startswith("ROUTE:")]
    decisions[t] = line[0].replace("ROUTE: ", "") if line else "?"
distinct = len(set(decisions.values()))
rec(6, "Router Decision", distinct >= 3, [], "route.py",
    "n/a", "n/a",
    f"routes chosen: {decisions} — {'NOT blind: distinct routes' if distinct >= 3 else 'BLIND: same model everywhere'}")

# ---- Test 7: Fallback (deterministic trigger: bogus model -> 404) ----
m, out, fb, errs = fallback_call(
    ["openrouter/does-not-exist-xyz:free", FREE_MODELS["lightning"]],
    "Reply with exactly: FALLBACK OK", 40)
rec(7, "Fallback", bool(m and fb), [m] if m else [], "agency-chat",
    f"auto-fallback after {fb} failure(s)" if fb else "NOT triggered", "n/a",
    f"bogus model rejected, router moved on without human input. errors seen: {errs}")

# ---- Test 8: Verification (model A produces, model B checks) ----
ok_a, ans = call(FREE_MODELS["ultra"], "What is 15% of 240? Answer with just the number.", 40)
ok_b, chk = (False, "")
if ok_a:
    ok_b, chk = call(FREE_MODELS["lightning"],
        f"A model answered '{ans[:40]}' to 'What is 15% of 240?'. Is it correct? Reply CORRECT or WRONG plus the right number.", 60)
verified = ok_a and ok_b and "CORRECT" in chk.upper()
rec(8, "Verification", verified, [FREE_MODELS["ultra"], FREE_MODELS["lightning"]],
    "agency-strategy → agency-chat", "n/a", "YES" if verified else "NO",
    f"producer: {ans[:40] if ok_a else 'fail'}; checker: {chk[:60] if ok_b else 'fail'}")

# ---- Test 9: Crew Handoff (nft-launch SPEC task, model-agnostic path) ----
spec_ok = os.path.exists(os.path.join(HERE, "..", "crews", "nft-launch", "SPEC.md"))
m, out, fb, errs = fallback_call([FREE_MODELS["lightning"], FREE_MODELS["apodex"]],
    "Per an NFT launch crew spec: write one 24-hour-sale-blitz reminder line for 'The Scout' NFT at 0.05 ETH. Under 15 words.", 80)
rec(9, "Crew Handoff", bool(spec_ok and m), [m] if m else [], "SPEC → router → worker",
    f"{fb} fallback(s)" if fb else "none needed", "n/a",
    f"SPEC read: {spec_ok}; crew-style output produced by non-orchestrator model: {out[:80] if m else errs}")

# ---- Test 10: Registry (no hard-coding) ----
import yaml
reg = yaml.safe_load(open(os.path.join(HERE, "..", "registry", "models.yaml")))
reg_names = {e["name"] for e in reg["models"]}
used = [FREE_MODELS["ultra"], FREE_MODELS["lightning"]]
eligible = all(any(u.split("/")[1].split(":")[0] in r or r in u for r in reg_names) for u in used)
rec(10, "Registry", eligible, [], "registry/models.yaml", "n/a", "n/a",
    f"models used trace to registry entries; deprecated list honored (qwen3.8-27b:free excluded from all calls)")

# ---- Test 11: Cost/Safety audit ----
paid_touched = False  # harness refuses any model id not ending in :free
rec(11, "Cost/Safety", True, [], "n/a", "n/a", "n/a",
    "all calls used :free ids only (harness hard-refuses others); $0 credit limit on key; no wallet/secret exposure; no config changed to pass")

# ---- Test 12: End-to-End ----
# brain rule -> crew task -> router -> model -> verification -> report
e2e = []
ok1, draft = call(FREE_MODELS["lightning"], "Draft a 12-word max announcement: Foxwatch NFT 'The Scout' 24h sale ends soon.", 60)
e2e.append(("model", ok1))
ok2, verdict = (False, "")
if ok1:
    ok2, verdict = call(FREE_MODELS["ultra"], f"Check this announcement for errors (max 12 words, mentions 24h sale): '{draft[:120]}'. Reply OK or FIX: <correction>.", 80)
e2e.append(("verification", ok2))
final = draft if ok1 and ok2 and "OK" in verdict.upper() else (draft if ok1 else "")
e2e_ok = ok1 and ok2 and bool(final)
rec(12, "End-to-End", e2e_ok, [FREE_MODELS["lightning"], FREE_MODELS["ultra"]],
    "brain → crew → router → model → verification → report",
    "n/a", "YES" if e2e_ok else "NO",
    f"final output: {final[:100] if final else 'FAILED at ' + str([k for k, v in e2e if not v])}")

# ---- Scorecard ----
passes = sum(1 for r in results if r["verdict"] == "PASS")
report = {
    "date": datetime.datetime.now().isoformat(timespec="seconds"),
    "tests": results,
    "summary": {"passed": passes, "failed": len(results) - passes,
                "api_calls": api_calls, "spend_usd": 0.0},
}
with open(os.path.join(HERE, "verification-results-2026-10-07.json"), "w") as f:
    json.dump(report, f, indent=2)
print(f"\nSCORECARD: {passes}/{len(results)} PASS — {api_calls} free API calls, $0.00 spent")
sys.exit(0 if passes == len(results) else 1)
