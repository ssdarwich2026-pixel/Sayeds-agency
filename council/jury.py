#!/usr/bin/env python3
"""Jury of Five — tier-1 executive council for Sayed's agency.

Sends one question to five free OpenRouter models in parallel (identical
neutral prompt), then one judge call synthesizes the VERDICT, including an
ESCALATION block that drafts a packet for the tier-2 In-Depth Crew when the
question is too big for the light jury.

Usage:
  python3 jury.py run "Your question here"
  python3 jury.py probe          # reachability-check the configured five + fallbacks

Rules honored (from the OpenRouter connector doc):
  - $0 only: config may contain :free model IDs only; enforced below.
  - Auth via the Secure Vault surrogate helpers only; the raw key is never
    seen, printed, or logged by this script.
  - Budget: checks `budget.py check N` before fan-out and records every HTTP
    attempt (serially, from the main thread — parallel record calls race the
    budget state file and lose counts).
"""
import concurrent.futures
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.yaml")
RUNS_DIR = os.path.join(HERE, "runs")

# dynamic_credentials lives in the connector-setup skill; the path moved once
# already (the legacy chat.py still points at the old one), so search both.
for _p in ("/opt/muse/skills/custom-connector-setup/bin",
           "/opt/muse/skills/custom-connector-setup/templates/skill/bin"):
    if os.path.exists(os.path.join(_p, "dynamic_credentials.py")):
        sys.path.insert(0, _p)
        break
from dynamic_credentials import add_surrogate_to_request, read_json_response  # noqa: E402

LABELS = ["A", "B", "C", "D", "E", "F"]


def load_config():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    ids = [m["id"] for m in cfg["models"]] + [cfg["judge"]["id"]]
    bad = [i for i in ids if not i.endswith(":free")]
    if bad:
        raise SystemExit(f"$0 RULE VIOLATION: non-free model IDs in config: {bad}")
    return cfg


def budget(cfg, *args):
    return subprocess.run([sys.executable, cfg["openrouter"]["budget_py"], *args],
                          capture_output=True, text=True, timeout=15)


def budget_record(cfg):
    budget(cfg, "record")


def call_model(cfg, model_id, prompt, max_tokens, counter):
    """One logical call (with configured retry on 429/5xx). Records every
    HTTP attempt against the daily free budget. Returns (text, error)."""
    orc = cfg["openrouter"]
    params = cfg["params"]
    body = json.dumps({
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    last_err = None
    for attempt in range(params["retries"] + 1):
        budget_record(cfg)
        counter["requests"] += 1
        req = urllib.request.Request(orc["api_url"], data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("HTTP-Referer", orc["referer"])
        req.add_header("X-Title", orc["title"])
        add_surrogate_to_request(req, orc["credential"],
                                 allowed_hosts=("openrouter.ai",))
        try:
            with urllib.request.urlopen(req, timeout=params["timeout_s"]) as resp:
                data = read_json_response(resp)
            if "choices" not in data:  # HTTP 200 with an error body (seen from NVIDIA pools)
                err = data.get("error", {})
                last_err = f"upstream error: {err.get('message', data)[:200]}"
                if attempt < params["retries"]:
                    time.sleep(params["retry_wait_s"])
                continue
            msg = data["choices"][0]["message"]
            text = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            if text:
                return text, None
            last_err = "empty response"
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode()[:300]
            except Exception:
                detail = "<unreadable>"
            last_err = f"HTTP {e.code}: {detail}"
            if e.code not in (429, 500, 502, 503):
                break
        except Exception as e:  # timeout, shape errors, etc.
            last_err = f"{type(e).__name__}: {e}"
        if attempt < params["retries"]:
            time.sleep(params["retry_wait_s"])
    return None, last_err


def slugify(text, n=6):
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "-".join(words) or "run"


def run(question):
    cfg = load_config()
    params = cfg["params"]
    models = cfg["models"]

    planned = len(models) + 1  # five jurors + one judge call
    chk = budget(cfg, "check", str(planned))
    if chk.returncode != 0:
        raise SystemExit(f"Budget check refused this run: {chk.stderr.strip()}")
    print(f"Budget: {chk.stdout.strip()}")

    counter = {"requests": 0}
    juror_prompt = cfg["prompts"]["juror"].format(question=question)

    def ask(model, delay=0):
        if delay:
            time.sleep(delay)
        return call_model(cfg, model["id"], juror_prompt,
                          params["juror_max_tokens"], counter)

    answers = {}   # label -> (model, text)
    failures = {}  # label -> (model, error)
    # Stagger starts: a simultaneous 5-way burst trips shared-pool concurrency
    # caps (NVIDIA returned "worker request limit reached" under burst).
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as ex:
        futs = {ex.submit(ask, m, i * 4): (LABELS[i], m)
                for i, m in enumerate(models)}
        for fut in concurrent.futures.as_completed(futs):
            label, model = futs[fut]
            text, err = fut.result()
            if text:
                answers[label] = (model, text)
            else:
                failures[label] = (model, err)
    # Recall pass: one more sequential attempt per failed juror after a
    # cooldown - free-tier 429s and pool caps are usually transient.
    if failures:
        print(f"Recall pass for {len(failures)} failed juror(s)...",
              file=sys.stderr)
        time.sleep(20)
        for label in sorted(failures):
            model, _ = failures[label]
            text, err = ask(model)
            if text:
                answers[label] = (model, text)
                del failures[label]
            else:
                failures[label] = (model, err)
    for label in sorted(failures):
        m, err = failures[label]
        print(f"WARNING: juror {label} ({m['id']}) failed: {err}", file=sys.stderr)
    if len(answers) < params["min_answers"]:
        verdict = (f"## VERDICT\nRun aborted: only {len(answers)} of "
                   f"{len(models)} jurors answered (minimum "
                   f"{params['min_answers']}). See failures in the log.")
        write_log(cfg, question, answers, failures, verdict, counter)
        print(verdict)
        return 1

    answers_block = "\n\n".join(
        f"### Advisor {label} ({model['provider']})\n{text}"
        for label, (model, text) in sorted(answers.items()))
    judge_prompt = cfg["prompts"]["judge"].format(question=question,
                                                  answers=answers_block)
    verdict, err = call_model(cfg, cfg["judge"]["id"], judge_prompt,
                              params["judge_max_tokens"], counter)
    if not verdict:
        verdict = (f"## VERDICT\nJudge call failed: {err}\n\n"
                   f"The five answers are preserved in the run log.")
        write_log(cfg, question, answers, failures, verdict, counter)
        print(verdict)
        return 1

    path = write_log(cfg, question, answers, failures, verdict, counter)
    print(f"\n=== JURY OF FIVE VERDICT ===\n{verdict}")
    print(f"\nRun log: {path}")
    print(f"OpenRouter requests used this run: {counter['requests']}")
    return 0


def write_log(cfg, question, answers, failures, verdict, counter):
    os.makedirs(RUNS_DIR, exist_ok=True)
    now = datetime.datetime.now()
    path = os.path.join(
        RUNS_DIR, f"{now:%Y-%m-%d-%H%M%S}-{slugify(question)}.md")
    lines = [
        f"# Jury of Five — run log",
        f"- When: {now:%Y-%m-%d %H:%M:%S} (local)",
        f"- Question: {question}",
        f"- Judge: {cfg['judge']['id']}",
        f"- OpenRouter requests used: {counter['requests']}",
        "",
        "## The five answers",
    ]
    for label in LABELS[:len(cfg["models"])]:
        if label in answers:
            model, text = answers[label]
            lines += [f"\n### Advisor {label} — {model['id']} "
                      f"({model['provider']}, {model['seat']})\n", text]
        elif label in failures:
            model, err = failures[label]
            lines += [f"\n### Advisor {label} — {model['id']}\n",
                      f"FAILED: {err}"]
    lines += ["", "## Verdict", "", verdict, ""]
    with open(path, "w") as f:
        f.write("\n".join(lines))
    return path


def probe():
    cfg = load_config()
    targets = [(m["id"], "seat") for m in cfg["models"]]
    targets += [(f["id"], "fallback") for f in cfg.get("fallbacks", [])]
    chk = budget(cfg, "check", str(len(targets)))
    if chk.returncode != 0:
        raise SystemExit(f"Budget check refused probe: {chk.stderr.strip()}")
    counter = {"requests": 0}
    for model_id, kind in targets:
        text, err = call_model(cfg, model_id,
                               "Reply with exactly one word: READY", 200, counter)
        status = f"OK ({text[:40]!r})" if text else f"FAIL: {err}"
        print(f"{kind:8s} {model_id}: {status}")
    print(f"Requests used: {counter['requests']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "probe":
        sys.exit(probe())
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        sys.exit(run(" ".join(sys.argv[2:])))
    print(__doc__)
    sys.exit(2)
