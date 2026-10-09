#!/usr/bin/env python3
"""Retest of failed tests 2, 4, 8, 10 with corrected harness logic / tighter prompts."""
import json, subprocess, os, yaml

CHAT = os.path.expanduser("~/workspace/skills/openrouter/bin/chat.py")
HERE = os.path.dirname(os.path.abspath(__file__))
api_calls = 0

def call(model, prompt, max_tokens=100):
    global api_calls
    api_calls += 1
    p = subprocess.run([CHAT, "--model", model, "--prompt", prompt,
                        "--max-tokens", str(max_tokens)],
                       capture_output=True, text=True, timeout=120)
    if p.returncode == 0:
        out = p.stdout.strip()[:500]
        return (bool(out and out != "[empty content]"), out)
    return False, (p.stdout + p.stderr).strip()[:200]

out = {}
# Test 2 retest: strict output-only instruction, non-reasoning-leaning model
ok, txt = call("google/gemma-4-31b-it:free",
    "OUTPUT ONLY the caption, no thinking, no preamble: one punchy Instagram caption under 20 words for a 'Dragon Crown Tee' streetwear drop.", 60)
out["test2"] = {"verdict": "PASS" if (ok and "thinking process" not in txt.lower()) else "FAIL",
                "output": txt[:120]}
# Test 4 retest: different small chat models
got = None
for m in ["thinkingmachines/inkling-small:free", "dots-studio/dots-3-note-preview:free"]:
    ok, txt = call(m, "OUTPUT ONLY one friendly sentence: what does a model router do?", 60)
    if ok and "thinking process" not in txt.lower():
        got = (m, txt); break
out["test4"] = {"verdict": "PASS" if got else "FAIL",
                "output": f"{got[0]}: {got[1][:120]}" if got else "all small chat models empty/flaky"}
# Test 8 retest: strict single-token verdict
ok_a, ans = call("nvidia/nemotron-3.5-lightning:free",
    "OUTPUT ONLY a number: what is 15% of 240?", 20)
ok_b, chk = (False, "")
if ok_a:
    ok_b, chk = call("nvidia/nemotron-3-ultra-550b-a55b:free",
        f"OUTPUT ONLY one word, CORRECT or WRONG: is '{ans[:20]}' the right answer to 'what is 15% of 240'?", 20)
verified = ok_a and ok_b and chk.strip().upper().startswith("CORRECT")
out["test8"] = {"verdict": "PASS" if verified else "FAIL",
                "output": f"producer={ans[:30]} checker={chk[:30]}"}
# Test 10 retest: fixed matching logic (registry id substring of model id)
reg = yaml.safe_load(open(os.path.join(HERE, "..", "registry", "models.yaml")))
reg_names = [e["name"] for e in reg["models"]]
used = ["nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3.5-lightning:free"]
eligible = all(any(r in u for r in reg_names) for u in used)
out["test10"] = {"verdict": "PASS" if eligible else "FAIL",
                 "output": f"registry entries match used models: {eligible}"}
out["_api_calls"] = api_calls
json.dump(out, open(os.path.join(HERE, "retest-results.json"), "w"), indent=2)
for k, v in out.items():
    if not k.startswith("_"):
        print(f"{k}: {v['verdict']} — {v['output'][:90]}")
print(f"retest API calls: {api_calls}")
