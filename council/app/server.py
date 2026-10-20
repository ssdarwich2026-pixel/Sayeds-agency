#!/usr/bin/env python3
"""Jury of Five — Room 1 web app, plus Room 2 (Jury of 45+) intake.

A single stdlib http.server service that wraps council/jury.py (or the
mock engine) so one non-technical user can ask questions and read verdicts
from a phone. No dependencies, no database, no build step.

Room 2 serves the Jury of 45+ INTAKE stage only: a question gets a
complexity score, the studio departments it would route to, and a rough
time estimate for the full run. The full 45+ engine is a later phase —
intake never starts one, and its result page says NOT YET WIRED.

Env vars:
  JURY_APP_PASSCODE  If set, a passcode gate protects the app (form + cookie).
                     If unset, the gate is DISABLED and a warning is shown.
  JURY_ENGINE_CMD    Engine command, e.g. "python3 council/mock_jury.py".
                     Default: "python3 council/jury.py".
  JURY_APP_MOCK      If "1", use council/mock_jury.py (unless JURY_ENGINE_CMD
                     is set explicitly).
  JURY_APP_PORT      Port to listen on. Default 8765.
  JURY_APP_HOST      Bind host. Default 127.0.0.1 (localhost only).

The app never sees, displays, or logs any API credential — it only ever
invokes the engine as a subprocess, exactly like running it in a terminal.
"""
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import threading
import time
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
COUNCIL_DIR = os.path.dirname(APP_DIR)
REPO_ROOT = os.path.dirname(COUNCIL_DIR)
CONFIG_PATH = os.path.join(COUNCIL_DIR, "config.yaml")
RUNS_DIR = os.path.join(COUNCIL_DIR, "runs")
MOCK_RUNS_DIR = os.path.join(COUNCIL_DIR, "mock-runs")
INTAKE_RUNS_DIR = os.path.join(COUNCIL_DIR, "intake-runs")
MOCK_INTAKE_RUNS_DIR = os.path.join(COUNCIL_DIR, "mock-intake-runs")
REGISTRY_PATH = os.path.join(REPO_ROOT, "registry", "models.yaml")

PASSCODE = os.environ.get("JURY_APP_PASSCODE", "")
PORT = int(os.environ.get("JURY_APP_PORT", "8765"))
HOST = os.environ.get("JURY_APP_HOST", "127.0.0.1")

SESSIONS = set()
JOBS = {}
JOBS_LOCK = threading.Lock()

# ---------------------------------------------------------------- engine ---

def is_mock_mode():
    if os.environ.get("JURY_APP_MOCK") == "1":
        return True
    return "mock_jury" in os.environ.get("JURY_ENGINE_CMD", "")


def resolve_engine_cmd():
    """Return the engine command as an argv list (without 'run'/question).

    Paths ending in .py are resolved against the repo root, then the
    council dir, so "python3 council/jury.py", "python3 jury.py"-style
    values and the mock equivalent all work from any working directory.
    """
    raw = os.environ.get("JURY_ENGINE_CMD", "")
    if not raw:
        raw = ("python3 council/mock_jury.py" if is_mock_mode()
               else "python3 council/jury.py")
    tokens = shlex.split(raw)
    out = []
    for tok in tokens:
        if tok in ("python", "python3"):
            out.append(sys.executable)
        elif tok.endswith(".py") and not os.path.isabs(tok):
            cands = [os.path.join(REPO_ROOT, tok),
                     os.path.join(COUNCIL_DIR, os.path.basename(tok)),
                     os.path.join(COUNCIL_DIR, tok)]
            out.append(next((c for c in cands if os.path.exists(c)), cands[0]))
        else:
            out.append(tok)
    return out


def budget_line():
    """Today's remaining free-request budget, from the connector budget
    tool referenced in council/config.yaml. Never hard-coded: if the tool
    cannot be read, returns a plain-language 'unavailable' line."""
    try:
        with open(CONFIG_PATH) as f:
            m = re.search(r"budget_py:\s*(\S+)", f.read())
        if not m:
            return None
        budget_py = m.group(1)
        r = subprocess.run([sys.executable, budget_py, "status"],
                           capture_output=True, text=True, timeout=10)
        m2 = re.search(r"remaining=(\d+)", r.stdout or "")
        if m2:
            return int(m2.group(1))
        r = subprocess.run([sys.executable, budget_py, "check", "0"],
                           capture_output=True, text=True, timeout=10)
        m3 = re.search(r"\((\d+) remaining\)", (r.stdout or "") + (r.stderr or ""))
        if m3:
            return int(m3.group(1))
    except Exception:
        pass
    return None


def budget_html():
    n = budget_line()
    if n is None:
        return ("Today&rsquo;s free-request budget: <strong>unavailable "
                "right now</strong> &mdash; the jury can still be asked, "
                "but please go easy.")
    return (f"Today&rsquo;s free-request budget: "
            f"<strong>{n} requests left</strong>")

# ------------------------------------------------------- Room 2: intake ---
# The Jury of 45+ (In-Depth Crew) starts with an INTAKE assessment, never
# with the full run. Intake scores the question, names the studio
# departments it would route to, and gives a rough time estimate for the
# full run. The full-run engine is a LATER phase: nothing in this section
# starts one, and the result page says so plainly ("NOT YET WIRED").
#
# Modes, following the Room 1 pattern:
#   mock      (JURY_APP_MOCK=1 / mock engine) — deterministic heuristic,
#             offline, $0, labeled MOCK, logs to mock-intake-runs/.
#   live      — ONE budget-checked OpenRouter :free call (the config's
#             judge model) asked for a strict-JSON assessment; the raw
#             credential is resolved by the connector surrogate helper,
#             exactly as council/jury.py does — never seen by this app.
#   heuristic — the same scoring code as mock mode, used as the live
#             fallback whenever the live call cannot run (budget refused,
#             pool busy, unparseable answer). Labeled as a fallback.

# The five studio departments (canonical list — the same five named in
# council/mock_jury.py's escalation packet and the tier-2 design:
# strategy, creative, legal/IP, market, money). q_words route a question;
# reg_words / reg_types tag registry models (registry/models.yaml,
# best_for + type fields) as examples of the pool a department draws on.
DEPARTMENTS = [
    {"key": "strategy", "name": "Strategy",
     "brief": "Direction, sequencing, trade-offs, and the final synthesis.",
     "q_words": ("strategy", "decide", "decision", "should we", "plan",
                 "priority", "priorities", "roadmap", "choose", "choice",
                 "direction", "launch", "expand", "pivot", "grow"),
     "reg_words": ("strategy", "reasoning", "decision", "long-context",
                   "planning"),
     "reg_types": ()},
    {"key": "creative", "name": "Creative",
     "brief": "Design, brand, content, and anything the audience sees.",
     "q_words": ("design", "brand", "logo", "video", "content", "shirt",
                 "creative", "name for", "naming", "copy", "image", "art",
                 "photo", "story", "campaign", "look and feel", "style"),
     "reg_words": ("copywriting", "design", "mockup", "brand", "speech",
                   "trend scan"),
     "reg_types": ("image", "video", "audio")},
    {"key": "legal-ip", "name": "Legal / IP",
     "brief": "Contracts, trademark / copyright, licensing, and risk of "
              "getting told to stop.",
     "q_words": ("contract", "legal", "trademark", "copyright", "licence",
                 "license", "licensing", "patent", "intellectual property",
                 " terms", "privacy", "compliance", "sue", "lawsuit",
                 "rights to", "permission to use", " ip "),
     "reg_words": ("legal", "licence", "license"),
     "reg_types": ()},
    {"key": "market", "name": "Market",
     "brief": "Customers, audience, competitors, demand, and channels.",
     "q_words": ("market", "customer", "audience", "competitor",
                 "competition", "sell", "sales", "demand", "niche",
                 "trend", "research", "survey", "who would buy",
                 "target market"),
     "reg_words": ("market", "trend", "research", "audience", "margin "
                   "analysis"),
     "reg_types": ()},
    {"key": "money", "name": "Money",
     "brief": "Price, cost, budget, revenue, margin, and whether the "
              "numbers survive contact with reality.",
     "q_words": ("money", "price", "pricing", "cost", "budget", "revenue",
                 "profit", "margin", "invest", "loan", "finance",
                 "financial", "spend", "spending", "$", "afford", "charge"),
     "reg_words": ("pricing", "margin", "finance", "money", "revenue",
                   "cost"),
     "reg_types": ()},
]
DEPT_BY_NAME = {d["name"].lower(): d for d in DEPARTMENTS}

HIGH_RISK_WORDS = ("contract", "legal", "trademark", "copyright", "spend",
                   "money", "invest", "loan", "hire", "launch", "lawsuit",
                   "irreversible", "sign a", "sign the", "$", "borrow")

# Rough working-time ranges (minutes) for a full 45+ run, by band. The
# full crew design is several rounds (draft, critique, refine, IP screen,
# synthesis) across every routed department on a shared free pool where
# 429 retries are routine — so even a "simple" crew run is not quick.
ETA_BASE_MINUTES = {"Simple": (20, 40), "Moderate": (40, 80),
                    "Complex": (75, 150), "Major": (150, 300)}


def load_registry_models():
    """Parse registry/models.yaml with a small line parser (the app is
    stdlib-only, so no PyYAML). Returns usable models only: entries whose
    best_for marks them NONE / research-only for this agency are excluded.
    Returns [] when the registry cannot be read."""
    try:
        with open(REGISTRY_PATH) as f:
            text = f.read()
    except Exception:
        return []
    # Only the top-level `models:` section counts — the registry also
    # lists tools: and deprecated: entries at the same indent, and a
    # router or an automation tool is not a crew model.
    sec = re.search(r"(?ms)^models:\s*\n(.*?)(?=^\S|\Z)", text)
    if sec:
        text = sec.group(1)
    models = []
    chunks = re.split(r"(?m)^  - name:\s*", text)
    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        name = lines[0].strip().strip("'\"") if lines else ""
        fields = {}
        for ln in lines[1:]:
            m = re.match(r"^\s{4}(\w+):\s*(.*)$", ln)
            if m:
                fields[m.group(1)] = m.group(2).strip().strip("'\"")
        best_for = fields.get("best_for", "")
        if not name or best_for.upper().startswith("NONE"):
            continue
        models.append({"name": name, "type": fields.get("type", ""),
                       "best_for": best_for,
                       "access": fields.get("access", "")})
    return models


def department_pool(dept, models):
    """Registry models tagged (best_for / type) for one department."""
    out = []
    for m in models:
        hay = (m["best_for"] + " " + m["type"]).lower()
        if m["type"].lower() in dept["reg_types"] or \
                any(w in hay for w in dept["reg_words"]):
            out.append(m)
    return out


def complexity_band(score):
    if score <= 3:
        return "Simple"
    if score <= 6:
        return "Moderate"
    if score <= 8:
        return "Complex"
    return "Major"


def run_history_calibration():
    """Calibrate the ETA from past Jury of Five runs under council/runs/.

    Run logs carry no wall-clock duration (the log is written at the end
    of a run), but they do record the OpenRouter request count, and pool
    congestion — retries and recalls — is what stretches real time. So:
    scale = average requests per past run / 6 (a clean run), clamped.
    With no usable history, scale is 1.0 and the basis says so."""
    counts = []
    if os.path.isdir(RUNS_DIR):
        for name in os.listdir(RUNS_DIR):
            if not name.endswith(".md"):
                continue
            try:
                with open(os.path.join(RUNS_DIR, name)) as f:
                    m = re.search(r"OpenRouter requests used:\s*(\d+)",
                                  f.read())
                if m:
                    counts.append(int(m.group(1)))
            except Exception:
                continue
    if not counts:
        return 1.0, ("No past Jury of Five runs found under council/runs/, "
                      "so this estimate uses the uncalibrated base range.")
    avg = sum(counts) / len(counts)
    scale = min(1.25, max(0.8, avg / 6.0))
    return scale, (f"Calibrated from {len(counts)} past Jury of Five "
                   f"run(s) under council/runs/ (average {avg:.1f} "
                   f"requests per run vs 6 for a clean run; busier pools "
                   f"mean more retries, so the range is scaled x{scale:.2f}).")


def fmt_minutes(m):
    m = int(round(m / 5.0) * 5) or 5
    if m < 60:
        return f"{m} minutes"
    h = m / 60.0
    hs = f"{h:.1f}".rstrip("0").rstrip(".")
    return f"{hs} hour" + ("" if hs == "1" else "s")


def estimate_eta(score, n_departments):
    band = complexity_band(score)
    lo, hi = ETA_BASE_MINUTES[band]
    scale, basis = run_history_calibration()
    return (f"about {fmt_minutes(lo * scale)} to {fmt_minutes(hi * scale)}",
            basis)


def heuristic_intake(question):
    """Deterministic complexity scoring + department routing. Used for
    mock mode and as the live-mode fallback. Returns an assessment dict
    (departments hold registry-pool info, added by the caller)."""
    q = " " + question.lower() + " "
    signals = []
    score = 2
    words = len(question.split())
    if words >= 20:
        score += 1
        signals.append(f"A long question ({words} words) — more moving "
                       f"parts to untangle.")
    if words >= 45:
        score += 1
        signals.append("A very detailed question — the crew would need "
                       "several passes to cover it all.")
    if words >= 80:
        score += 1
    routed = []
    for dept in DEPARTMENTS:
        hits = [w for w in dept["q_words"] if w in q]
        if hits:
            routed.append(dept)
            signals.append(f"{dept['name']} territory: the question "
                           f"mentions {', '.join(sorted(set(h.strip() for h in hits))[:3])}.")
    if len(routed) >= 2:
        score += 1
    if len(routed) >= 4:
        score += 1
        signals.append(f"It spans {len(routed)} departments — cross-"
                       f"department questions are the heavy ones.")
    risk_hits = sorted({w for w in HIGH_RISK_WORDS if w in q})
    if risk_hits:
        score += 1
        signals.append("Money / legal / commitment signals: "
                       + ", ".join(risk_hits[:4]) + ".")
    if len(risk_hits) >= 3:
        score += 1
    clauses = q.count(",") + q.count(";") + q.count(" and ")
    if clauses >= 3:
        score += 1
        signals.append("Several linked sub-questions in one — each one "
                       "needs its own pass.")
    if not routed:
        routed = [DEPARTMENTS[0]]
        signals.append("No single department stands out — Strategy would "
                       "take the first pass and route from there.")
    if not signals:
        signals.append("A short, single-topic question with no money, "
                       "legal, or launch signals.")
    score = max(1, min(10, score))
    watch = ["Free-tier reality: the full crew shares the ~50-request/day "
             "free pool, so a full run may queue across more than one "
             "day. The estimate is working time once the run starts, "
             "not queue time."]
    if risk_hits:
        watch.insert(0, "This question carries money / legal / commitment "
                        "signals — that is exactly what the 45+ crew "
                        "exists to check before anyone acts.")
    return {"score": score, "band": complexity_band(score),
            "departments": routed, "signals": signals, "watch_outs": watch,
            "source": "heuristic"}


def live_intake(question):
    """One budget-checked OpenRouter :free call for a JSON assessment,
    following council/jury.py's patterns (config-driven, surrogate
    credential helper, budget check + record). Returns (assessment,
    None) on success or (None, short_reason) — the caller falls back to
    the heuristic either way, so intake always answers."""
    try:
        with open(CONFIG_PATH) as f:
            cfg_text = f.read()
    except Exception:
        return None, "council config could not be read"

    def cfg1(pattern):
        m = re.search(pattern, cfg_text)
        return m.group(1).strip() if m else ""

    api_url = cfg1(r"api_url:\s*(\S+)")
    credential = cfg1(r"credential:\s*(\S+)")
    referer = cfg1(r"referer:\s*(\S+)")
    title = cfg1(r"(?m)^\s*title:\s*(.+)$")
    budget_py = cfg1(r"budget_py:\s*(\S+)")
    m = re.search(r"(?ms)^judge:\s*\n\s*id:\s*(\S+)", cfg_text)
    model_id = m.group(1).strip() if m else ""
    if not model_id.endswith(":free"):
        return None, "configured intake model is not a :free model"
    if not (api_url and credential and budget_py):
        return None, "council config is incomplete for a live call"

    def budget(*args):
        return subprocess.run([sys.executable, budget_py, *args],
                              capture_output=True, text=True, timeout=15)

    try:
        chk = budget("check", "1")
        if chk.returncode != 0:
            return None, "the free-request budget check refused the call"
    except Exception:
        return None, "the free-request budget could not be checked"

    helper = None
    for p in ("/opt/muse/skills/custom-connector-setup/bin",
              "/opt/muse/skills/custom-connector-setup/templates/skill/bin"):
        if os.path.exists(os.path.join(p, "dynamic_credentials.py")):
            helper = p
            break
    if not helper:
        return None, "the credential helper is unavailable"
    if helper not in sys.path:
        sys.path.insert(0, helper)
    try:
        from dynamic_credentials import (add_surrogate_to_request,
                                         read_json_response)
    except Exception:
        return None, "the credential helper could not be loaded"

    dept_names = ", ".join(d["name"] for d in DEPARTMENTS)
    prompt = (
        "You are the intake assessor for a 45-model executive crew with "
        f"these studio departments: {dept_names}. Assess the question "
        "below for a full crew run. Reply with ONLY a JSON object, no "
        "other text, in exactly this shape:\n"
        '{"complexity_score": <integer 1-10>, "departments": [<department '
        'names from the list above>], "rationale": "<one or two sentences>", '
        '"watch_outs": "<one sentence, or empty>"}\n'
        "Score 1-3 = simple single-topic; 4-6 = moderate, a few angles; "
        "7-8 = complex, several departments or real money/legal risk; "
        "9-10 = major launch-scale commitment.\n\n"
        f"QUESTION: {question}")
    body = json.dumps({"model": model_id,
                       "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": 700}).encode()
    import urllib.error
    import urllib.request
    try:
        budget("record")
        req = urllib.request.Request(api_url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if referer:
            req.add_header("HTTP-Referer", referer)
        if title:
            req.add_header("X-Title", title)
        add_surrogate_to_request(req, credential,
                                 allowed_hosts=("openrouter.ai",))
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = read_json_response(resp)
        if "choices" not in data:
            return None, "the free pool returned an error body"
        msg = data["choices"][0]["message"]
        text = (msg.get("content") or msg.get("reasoning_content") or "")
        jm = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(jm.group(0)) if jm else None
        if not parsed:
            return None, "the live answer could not be parsed"
        score = max(1, min(10, int(parsed.get("complexity_score", 0))))
        routed = []
        for name in parsed.get("departments") or []:
            dept = DEPT_BY_NAME.get(str(name).strip().lower())
            if dept and dept not in routed:
                routed.append(dept)
        if not routed:
            routed = heuristic_intake(question)["departments"]
        signals = []
        if parsed.get("rationale"):
            signals.append(str(parsed["rationale"]).strip())
        signals.append(f"Live intake by {model_id} (1 free request, "
                       f"budget-checked before the call).")
        watch = []
        if parsed.get("watch_outs"):
            watch.append(str(parsed["watch_outs"]).strip())
        watch.append("Free-tier reality: the full crew shares the "
                     "~50-request/day free pool, so a full run may queue "
                     "across more than one day. The estimate is working "
                     "time once the run starts, not queue time.")
        return {"score": score, "band": complexity_band(score),
                "departments": routed, "signals": signals,
                "watch_outs": watch, "source": "live"}, None
    except Exception:
        return None, "the free pool did not answer"


def assess_intake(question):
    """Run one intake assessment (mock / live / heuristic fallback),
    enrich it with registry pools + the calibrated ETA, persist it as a
    run-log-style markdown file, and return (assessment, intake_id)."""
    started = time.time()
    if is_mock_mode():
        a = heuristic_intake(question)
        a["source"] = "mock"
        a["mode_label"] = "MOCK — heuristic assessment, no live calls, $0"
    else:
        live, reason = live_intake(question)
        if live is not None:
            a = live
            a["mode_label"] = "Live intake (1 budget-checked free request)"
        else:
            a = heuristic_intake(question)
            a["mode_label"] = ("Heuristic assessment — live intake was "
                               f"unavailable ({reason}), so the built-in "
                               "scorer answered instead. No budget spent.")
    models = load_registry_models()
    a["pools"] = {d["key"]: department_pool(d, models)
                  for d in a["departments"]}
    a["registry_count"] = len(models)
    a["eta"], a["eta_basis"] = estimate_eta(a["score"],
                                            len(a["departments"]))
    a["question"] = question
    a["when"] = time.strftime("%Y-%m-%d %H:%M:%S")
    a["elapsed_s"] = round(time.time() - started, 1)
    intake_id = write_intake_log(a)
    return a, intake_id


def intake_slug(text, n=6):
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "-".join(words) or "intake"


def write_intake_log(a):
    mock = a["source"] == "mock"
    d = MOCK_INTAKE_RUNS_DIR if mock else INTAKE_RUNS_DIR
    os.makedirs(d, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S")
    name = f"{stamp}-{'MOCK-' if mock else ''}{intake_slug(a['question'])}.md"
    dept_lines = []
    for dept in a["departments"]:
        pool = a["pools"].get(dept["key"], [])
        examples = ", ".join(m["name"] for m in pool[:3])
        dept_lines.append(
            f"- **{dept['name']}** — {dept['brief']} "
            f"(registry pool tagged for this department: {len(pool)} "
            f"model(s){': ' + examples if examples else ' — none tagged yet, routing is by department brief'})")
    lines = [
        "# Jury of 45+ — intake assessment" + (" [MOCK]" if mock else ""),
        f"- When: {a['when']} (local)",
        f"- Question: {a['question']}",
        f"- Mode: {a['mode_label']}",
        f"- Complexity score: {a['score']} / 10 ({a['band']})",
        f"- Departments: {', '.join(d['name'] for d in a['departments'])}",
        f"- Time estimate for the full run: {a['eta']}",
        f"- Estimate basis: {a['eta_basis']}",
        f"- Intake took: {a['elapsed_s']}s",
        "",
        "## Why this score",
        "",
        *[f"- {s}" for s in a["signals"]],
        "",
        "## Departments it would route to",
        "",
        *dept_lines,
        "",
        "## Watch-outs",
        "",
        *[f"- {w}" for w in a["watch_outs"]],
        "",
        "## Full run status",
        "",
        "NOT YET WIRED — the full 45+ engine is a later phase. This "
        "intake assessment does not start a full run, and no crew run "
        "has been queued.",
        "",
    ]
    with open(os.path.join(d, name), "w") as f:
        f.write("\n".join(lines))
    label = "mock-intake-runs" if mock else "intake-runs"
    return f"{label}/{name}"


def parse_intake_text(text):
    out = {"question": "", "when": "", "mode": "", "score": "",
           "band": "", "departments_line": "", "eta": "", "basis": "",
           "mock": "[MOCK]" in text[:200], "raw": text, "sections": {}}
    for line in text.splitlines():
        for label, key in (("- Question:", "question"), ("- When:", "when"),
                           ("- Mode:", "mode"), ("- Time estimate for the "
                            "full run:", "eta"),
                           ("- Estimate basis:", "basis"),
                           ("- Departments:", "departments_line")):
            if line.startswith(label):
                out[key] = line.split(":", 1)[1].strip()
        m = re.match(r"- Complexity score:\s*(\d+)\s*/\s*10\s*\(([^)]+)\)",
                     line)
        if m:
            out["score"], out["band"] = m.group(1), m.group(2)
    secs = re.split(r"(?m)^##\s+(.+)$", text)
    for i in range(1, len(secs) - 1, 2):
        out["sections"][secs[i].strip()] = secs[i + 1].strip()
    return out


def list_intakes():
    """Past intake assessments, newest first. Mock intakes are included
    in mock mode (same convention as Room 1 history)."""
    entries = []
    dirs = [("intake-runs", INTAKE_RUNS_DIR)]
    if is_mock_mode():
        dirs.append(("mock-intake-runs", MOCK_INTAKE_RUNS_DIR))
    for label, d in dirs:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".md"):
                continue
            path = os.path.join(d, name)
            try:
                with open(path) as f:
                    parsed = parse_intake_text(f.read())
                entries.append({"id": f"{label}/{name}",
                                "question": parsed["question"] or name,
                                "when": parsed["when"],
                                "score": parsed["score"],
                                "band": parsed["band"],
                                "eta": parsed["eta"],
                                "mock": parsed["mock"] or label.startswith("mock"),
                                "mtime": os.path.getmtime(path)})
            except Exception:
                continue
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def load_intake(intake_id):
    """Load one intake log by id. Read-only; traversal refused."""
    label, _, name = (intake_id or "").partition("/")
    base = {"intake-runs": INTAKE_RUNS_DIR,
            "mock-intake-runs": MOCK_INTAKE_RUNS_DIR}.get(label)
    if not base or not name or "/" in name or "\\" in name \
            or not name.endswith(".md"):
        return None
    path = os.path.join(base, name)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return parse_intake_text(f.read())


INTAKE_JOBS = {}


def run_intake_job(job_id, question):
    def upd(**kw):
        with JOBS_LOCK:
            INTAKE_JOBS[job_id].update(kw)
    upd(status="running", stage="Intake is assessing…")
    try:
        _, intake_id = assess_intake(question)
        upd(status="done", stage="Intake assessment", intake_id=intake_id)
    except Exception:
        upd(status="error", stage="",
            error="Intake could not assess that question this time. "
                  "Please try again in a little while.")

# ------------------------------------------------------------- run logs ---

def parse_run_text(text):
    """Parse a jury/mock run log into the pieces the verdict view needs."""
    out = {"question": "", "when": "", "mock": "[MOCK]" in text[:300],
           "answers": [], "verdict": "", "disagreed": "",
           "confidence": "", "escalation": "", "raw": text}
    for line in text.splitlines():
        if line.startswith("- Question:"):
            out["question"] = line.split(":", 1)[1].strip()
        elif line.startswith("- When:"):
            out["when"] = line.split(":", 1)[1].strip()
    a = text.find("## The five answers")
    v = text.find("\n## Verdict")
    if a >= 0:
        chunk = text[a:v if v >= 0 else None]
        parts = re.split(r"(?m)^###\s+", chunk)
        for part in parts[1:]:
            title, _, body = part.partition("\n")
            out["answers"].append({"title": title.strip(),
                                   "body": body.strip(),
                                   "failed": body.strip().upper().startswith("FAILED")})
    if v >= 0:
        vchunk = text[v:]
        secs = re.split(r"(?m)^##\s+(VERDICT|WHERE THE FIVE DISAGREED|"
                        r"CONFIDENCE|ESCALATION)\s*$", vchunk)
        # secs: [pre, name, body, name, body, ...]
        keys = {"VERDICT": "verdict", "WHERE THE FIVE DISAGREED": "disagreed",
                "CONFIDENCE": "confidence", "ESCALATION": "escalation"}
        for i in range(1, len(secs) - 1, 2):
            if secs[i] in keys:
                out[keys[secs[i]]] = secs[i + 1].strip()
    return out


def list_runs():
    """History entries, newest first. Mock runs are included in mock mode."""
    entries = []
    dirs = [("runs", RUNS_DIR)]
    if is_mock_mode():
        dirs.append(("mock-runs", MOCK_RUNS_DIR))
    for label, d in dirs:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".md"):
                continue
            path = os.path.join(d, name)
            try:
                with open(path) as f:
                    parsed = parse_run_text(f.read())
                entries.append({"id": f"{label}/{name}",
                                "question": parsed["question"] or name,
                                "when": parsed["when"],
                                "mock": parsed["mock"] or label == "mock-runs",
                                "mtime": os.path.getmtime(path)})
            except Exception:
                continue
    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries


def load_run(run_id):
    """Load one run log by its id ('runs/<file>' or 'mock-runs/<file>').
    Read-only; path traversal is refused."""
    label, _, name = (run_id or "").partition("/")
    base = {"runs": RUNS_DIR, "mock-runs": MOCK_RUNS_DIR}.get(label)
    if not base or not name or "/" in name or "\\" in name \
            or not name.endswith(".md"):
        return None
    path = os.path.join(base, name)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return parse_run_text(f.read())

# -------------------------------------------------------------- rendering ---

def md_html(md):
    """A tiny, safe markdown-to-HTML renderer: paragraphs, bold, lists.
    Everything is escaped first — run-log content can never inject HTML."""
    if not md:
        return ""
    blocks, out = re.split(r"\n\s*\n", md.strip()), []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        def fmt(s):
            s = html.escape(s)
            s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
            return s
        if all(ln.startswith(("- ", "* ")) for ln in lines):
            out.append("<ul>" + "".join(f"<li>{fmt(ln[2:])}</li>"
                                        for ln in lines) + "</ul>")
        else:
            out.append("<p>" + "<br>".join(fmt(ln) for ln in lines) + "</p>")
    return "\n".join(out)


CSS = """
body{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#f6f6f4;color:#1c1c1a}
.wrap{max-width:720px;margin:0 auto;padding:16px}
h1{font-size:1.7rem;margin:.3em 0}
.tabs{display:flex;gap:8px;margin:12px 0 18px}
.tabs a{flex:1;text-align:center;padding:10px 4px;border-radius:10px;background:#e7e6e1;
color:#1c1c1a;text-decoration:none;font-weight:600;font-size:.95rem}
.tabs a.on{background:#1c1c1a;color:#fff}
.card{background:#fff;border-radius:14px;padding:16px;margin:12px 0;
box-shadow:0 1px 3px rgba(0,0,0,.08)}
textarea{width:100%;box-sizing:border-box;font-size:1.1rem;padding:12px;
border:2px solid #ccc;border-radius:10px;min-height:130px}
button.ask{width:100%;font-size:1.2rem;font-weight:700;padding:16px;margin-top:12px;
border:0;border-radius:12px;background:#166b3a;color:#fff}
button.ask:disabled{background:#9a9a94;cursor:not-allowed}
.score{font-size:2.2rem;font-weight:800;line-height:1.1}
.eta{font-size:1.3rem;font-weight:700}
button.copy{font-size:1rem;padding:10px 16px;border:0;border-radius:8px;
background:#1c1c1a;color:#fff}
.budget{font-size:1rem;color:#444}.warn{background:#fff3cd;border-radius:10px;padding:10px}
.answer{font-size:1.25rem;line-height:1.5}
details{margin:10px 0}summary{font-weight:700;cursor:pointer;padding:8px 0;font-size:1.05rem}
textarea.copybox{width:100%;box-sizing:border-box;min-height:150px;font-size:.95rem;
padding:10px;border-radius:8px;border:1.5px solid #aaa;background:#fafafa}
.hist a{display:block;color:#166b3a;font-weight:600;text-decoration:none;padding:6px 0}
.small{color:#666;font-size:.88rem}.err{background:#fdecea;border-radius:10px;padding:12px}
"""


def page(title, body, tab="ask"):
    tabs = "".join(
        f'<a href="{href}" class="{"on" if key == tab else ""}">{label}</a>'
        for key, href, label in (("ask", "/", "Ask the Jury"),
                                 ("history", "/history", "History"),
                                 ("room2", "/room2", "Jury of 45+")))
    warn = ('<p class="warn">Passcode gate is <strong>off</strong> '
            '(JURY_APP_PASSCODE is not set). Anyone who can reach this '
            'address can use the jury.</p>' if not PASSCODE else "")
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
            f"<body><div class='wrap'><h1>Jury of Five</h1>{warn}"
            f"<nav class='tabs'>{tabs}</nav>{body}</div></body></html>")


def verdict_html(p, run_id=""):
    answered = [a for a in p["answers"] if not a["failed"]]
    total = len(p["answers"]) or 5
    who = []
    for a in p["answers"]:
        m = re.match(r"(Advisor\s+\w+)\s*—\s*(\S+)(?:\s*\(([^,)]+)[^)]*\))?",
                     a["title"])
        if m:
            who.append(f"{m.group(1)} ({m.group(3) or m.group(2)})"
                       + ("" if not a["failed"] else " — did not answer"))
        else:
            who.append(a["title"])
    partial = ""
    if 0 < len(answered) < total:
        partial = (f"<p>The free pool was busy — only {len(answered)} of "
                   f"{total} jurors answered. That&rsquo;s still a valid "
                   f"verdict.</p>")
    jurors = "".join(
        f"<details><summary>{html.escape(a['title'])}</summary>"
        f"{md_html(a['body'])}</details>" for a in p["answers"])
    esc = p["escalation"]
    if "ESCALATION: YES" in esc.upper():
        esc_block = (f"<h2>Escalation</h2><p>This one should go up to the "
                     f"In-Depth Crew. Copy the packet below and hand it on:</p>"
                     f"<textarea class='copybox' id='escbox' readonly>"
                     f"{html.escape(esc)}</textarea>"
                     f"<p><button class='copy' onclick=\"navigator.clipboard."
                     f"writeText(document.getElementById('escbox').value)\">"
                     f"Copy the escalation packet</button></p>")
    elif esc:
        esc_block = f"<h2>Escalation</h2>{md_html(esc)}"
    else:
        esc_block = ""
    mock = " <span class='small'>[MOCK run — test content]</span>" if p["mock"] else ""
    return (f"<p class='small'>{html.escape(p['when'])}{mock}</p>"
            f"<div class='card'><h2 style='margin-top:0'>The question</h2>"
            f"<p>{html.escape(p['question'])}</p></div>"
            f"<div class='card'><h2 style='margin-top:0'>The jury&rsquo;s answer</h2>"
            f"<div class='answer'>{md_html(p['verdict'])}</div></div>"
            f"<div class='card'><h2 style='margin-top:0'>Who answered</h2>"
            f"<p><strong>{len(answered)} of {total} jurors answered.</strong></p>"
            f"{partial}<ul>{''.join(f'<li>{html.escape(w)}</li>' for w in who)}</ul></div>"
            f"<div class='card'><h2 style='margin-top:0'>Each juror&rsquo;s answer</h2>"
            f"{jurors}</div>"
            f"<div class='card'><h2 style='margin-top:0'>Where the five disagreed</h2>"
            f"{md_html(p['disagreed'])}</div>"
            f"<div class='card'><h2 style='margin-top:0'>Confidence</h2>"
            f"{md_html(p['confidence'])}</div>"
            f"<div class='card'>{esc_block}</div>")

# ------------------------------------------------------------------ jobs ---

def run_job(job_id, question):
    def upd(**kw):
        with JOBS_LOCK:
            JOBS[job_id].update(kw)
    upd(status="running", stage="Asking the five…")
    before = set()
    for d in (RUNS_DIR, MOCK_RUNS_DIR):
        if os.path.isdir(d):
            before |= {os.path.join(d, n) for n in os.listdir(d)}
    try:
        r = subprocess.run(resolve_engine_cmd() + ["run", question],
                           cwd=COUNCIL_DIR, capture_output=True, text=True,
                           timeout=900)
        run_id = None
        m = re.search(r"Run log:\s*(\S+)", r.stdout or "")
        if m and os.path.isfile(m.group(1)):
            path = os.path.abspath(m.group(1))
            label = "mock-runs" if "mock-runs" in path else "runs"
            run_id = f"{label}/{os.path.basename(path)}"
        if not run_id:  # fall back to the newest new file
            new = []
            for d, label in ((RUNS_DIR, "runs"), (MOCK_RUNS_DIR, "mock-runs")):
                if os.path.isdir(d):
                    new += [(os.path.getmtime(os.path.join(d, n)),
                             f"{label}/{n}")
                            for n in os.listdir(d)
                            if os.path.join(d, n) not in before]
            if new:
                run_id = sorted(new)[-1][1]
        if run_id:
            upd(status="done", stage="Verdict", run_id=run_id)
        else:
            upd(status="error", stage="",
                error="The jury did not produce a verdict this time. "
                      "The free pool may be busy — please try again in a "
                      "little while.")
    except subprocess.TimeoutExpired:
        upd(status="error", stage="",
            error="The jury took too long to answer. Please try again.")
    except Exception:
        upd(status="error", stage="",
            error="Something went wrong asking the jury. Please try again.")

# --------------------------------------------------------------- handler ---

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # keep the console (and any credential-adjacent noise) quiet

    # -- helpers
    def authed(self):
        if not PASSCODE:
            return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "jury_session" in c and c["jury_session"].value in SESSIONS

    def send_html(self, body, status=200, headers=None):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def login_page(self, msg=""):
        body = (f"{'<p class=err>' + html.escape(msg) + '</p>' if msg else ''}"
                "<div class='card'><h2 style='margin-top:0'>Enter the passcode</h2>"
                "<form method='post' action='/login'>"
                "<p><input type='password' name='passcode' "
                "style='width:100%;box-sizing:border-box;font-size:1.2rem;"
                "padding:12px;border:2px solid #ccc;border-radius:10px'></p>"
                "<button class='ask' type='submit'>Enter</button></form></div>")
        return page("Jury of Five — passcode", body)

    # -- routes
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/login":
            return self.send_html(self.login_page())
        if not self.authed():
            return self.send_html(self.login_page())
        if u.path == "/":
            body = (f"<p class='budget'>{budget_html()}</p>"
                    "<div class='card'><form id='askform'>"
                    "<label for='qq'><strong>What do you want the jury to "
                    "decide?</strong></label>"
                    "<textarea id='qq' name='question' "
                    "placeholder='Type your question here…'></textarea>"
                    "<button class='ask' type='submit'>Ask the Jury</button>"
                    "</form><p id='status' class='small'></p></div>"
                    "<script>"
                    "let poll=null;"
                    "document.getElementById('askform').onsubmit=async e=>{"
                    "e.preventDefault();"
                    "const question=document.getElementById('qq').value.trim();"
                    "const st=document.getElementById('status');"
                    "if(!question){st.textContent='Type a question first.';return;}"
                    "st.textContent='Asking the five…';"
                    "const r=await fetch('/api/ask',{method:'POST',"
                    "headers:{'Content-Type':'application/json'},"
                    "body:JSON.stringify({question})});"
                    "const j=await r.json();"
                    "if(j.error){st.textContent=j.error;return;}"
                    "if(j.note){st.textContent=j.note;}"
                    "clearInterval(poll);"
                    "poll=setInterval(async()=>{"
                    "const s=await (await fetch('/api/job/'+j.job_id)).json();"
                    "st.textContent=s.stage||s.status;"
                    "if(s.status==='done'){clearInterval(poll);"
                    "location.href='/verdict?f='+encodeURIComponent(s.run_id);}"
                    "if(s.status==='error'){clearInterval(poll);"
                    "st.textContent=s.error||'Something went wrong.';}"
                    "},3000);};"
                    "</script>")
            return self.send_html(page("Jury of Five", body, "ask"))
        if u.path == "/history":
            items = "".join(
                f"<div><a href='/verdict?f={urllib.parse.quote(e['id'])}'>"
                f"{html.escape(e['question'])}</a>"
                f"<span class='small'>{html.escape(e['when'])}"
                f"{' · MOCK' if e['mock'] else ''}</span></div>"
                for e in list_runs())
            body = (f"<div class='card hist'><h2 style='margin-top:0'>"
                    f"Past questions</h2>{items or '<p>No runs yet.</p>'}</div>")
            return self.send_html(page("Jury of Five — History", body, "history"))
        if u.path == "/room2":
            past = "".join(
                f"<div><a href='/room2/intake?f={urllib.parse.quote(e['id'])}'>"
                f"{html.escape(e['question'])}</a>"
                f"<span class='small'>{html.escape(e['when'])}"
                f"{' · score ' + html.escape(e['score']) + '/10 (' + html.escape(e['band']) + ')' if e['score'] else ''}"
                f"{' · MOCK' if e['mock'] else ''}</span></div>"
                for e in list_intakes()[:10])
            body = (
                f"<p class='budget'>{budget_html()}</p>"
                "<div class='card'><h2 style='margin-top:0'>Jury of 45+ — "
                "intake first</h2>"
                "<p>The In-Depth Crew never starts cold. Type a question "
                "and a small <strong>intake assessment</strong> runs "
                "first: it scores how complex the question is, names the "
                "studio departments it would route to, and gives a rough "
                "time estimate for the full run — <em>before</em> anything "
                "big is started.</p>"
                "<form id='intakeform'>"
                "<label for='iq'><strong>What do you want the 45+ crew "
                "to dig into?</strong></label>"
                "<textarea id='iq' name='question' "
                "placeholder='Type your question here…'></textarea>"
                "<button class='ask' type='submit'>Run intake "
                "assessment</button></form>"
                "<p id='istatus' class='small'></p></div>"
                f"<div class='card hist'><h2 style='margin-top:0'>Past "
                f"intake assessments</h2>"
                f"{past or '<p>No intake assessments yet.</p>'}</div>"
                "<script>"
                "let ipoll=null;"
                "document.getElementById('intakeform').onsubmit=async e=>{"
                "e.preventDefault();"
                "const question=document.getElementById('iq').value.trim();"
                "const st=document.getElementById('istatus');"
                "if(!question){st.textContent='Type a question first.';return;}"
                "st.textContent='Intake is assessing…';"
                "const r=await fetch('/api/intake',{method:'POST',"
                "headers:{'Content-Type':'application/json'},"
                "body:JSON.stringify({question})});"
                "const j=await r.json();"
                "if(j.error){st.textContent=j.error;return;}"
                "if(j.note){st.textContent=j.note;}"
                "clearInterval(ipoll);"
                "ipoll=setInterval(async()=>{"
                "const s=await (await fetch('/api/intake-job/'+j.job_id)).json();"
                "st.textContent=s.stage||s.status;"
                "if(s.status==='done'){clearInterval(ipoll);"
                "location.href='/room2/intake?f='+encodeURIComponent(s.intake_id);}"
                "if(s.status==='error'){clearInterval(ipoll);"
                "st.textContent=s.error||'Something went wrong.';}"
                "},1500);};"
                "</script>")
            return self.send_html(page("Jury of 45+", body, "room2"))
        if u.path == "/room2/intake":
            p = load_intake(q.get("f", [""])[0])
            if p is None:
                return self.send_html(page("Not found",
                    "<div class='card'><p>That intake assessment could "
                    "not be found.</p></div>"), status=404)
            secs = p["sections"]
            dept_html = md_html(secs.get("Departments it would route to", ""))
            mock = (" <span class='small'>[MOCK assessment — test "
                    "content]</span>" if p["mock"] else "")
            body = (
                f"<p class='small'>{html.escape(p['when'])}{mock}</p>"
                f"<div class='card'><h2 style='margin-top:0'>The question"
                f"</h2><p>{html.escape(p['question'])}</p>"
                f"<p class='small'>{html.escape(p['mode'])}</p></div>"
                f"<div class='card'><h2 style='margin-top:0'>Complexity</h2>"
                f"<p class='score'>{html.escape(p['score'])} / 10 "
                f"<span style='font-size:1.2rem'>({html.escape(p['band'])})"
                f"</span></p>{md_html(secs.get('Why this score', ''))}</div>"
                f"<div class='card'><h2 style='margin-top:0'>Departments "
                f"it would route to</h2>{dept_html}</div>"
                f"<div class='card'><h2 style='margin-top:0'>Time "
                f"estimate for the full run</h2>"
                f"<p class='eta'>{html.escape(p['eta'])}</p>"
                f"<p class='small'>{html.escape(p['basis'])}</p></div>"
                f"<div class='card'><h2 style='margin-top:0'>Watch-outs</h2>"
                f"{md_html(secs.get('Watch-outs', ''))}</div>"
                f"<div class='card'><h2 style='margin-top:0'>Full run</h2>"
                f"{md_html(secs.get('Full run status', ''))}"
                "<button class='ask' type='button' disabled>Start full "
                "run — NOT YET WIRED</button>"
                "<p class='small'>The full 45+ engine is a later phase. "
                "This button is disabled on purpose: intake never starts "
                "a full run by itself.</p></div>")
            return self.send_html(page("Jury of 45+ — Intake", body, "room2"))
        if u.path.startswith("/api/intake-job/"):
            job_id = u.path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = dict(INTAKE_JOBS.get(job_id) or {})
            if not job:
                return self.send_json({"error": "That job was not found."}, 404)
            return self.send_json({k: job.get(k) for k in
                                   ("status", "stage", "intake_id", "error")})
        if u.path == "/verdict":
            p = load_run(q.get("f", [""])[0])
            if p is None:
                return self.send_html(page("Not found",
                    "<div class='card'><p>That verdict could not be found.</p></div>"),
                    status=404)
            return self.send_html(page("Jury of Five — Verdict",
                                       verdict_html(p), "ask"))
        if u.path.startswith("/api/job/"):
            job_id = u.path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = dict(JOBS.get(job_id) or {})
            if not job:
                return self.send_json({"error": "That job was not found."}, 404)
            if job.get("status") == "running":
                elapsed = time.time() - job.get("started", time.time())
                job["stage"] = ("Asking the five…" if elapsed < 25
                                else "Cross-checking…")
            return self.send_json({k: job.get(k) for k in
                                   ("status", "stage", "run_id", "error")})
        return self.send_html(page("Not found",
            "<div class='card'><p>That page could not be found.</p></div>"),
            status=404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if u.path == "/login":
            form = urllib.parse.parse_qs(raw.decode(errors="replace"))
            given = (form.get("passcode") or [""])[0]
            if PASSCODE and hmac.compare_digest(given, PASSCODE):
                token = secrets.token_urlsafe(32)
                SESSIONS.add(token)
                return self.send_html(
                    page("Jury of Five",
                         "<div class='card'><p>Welcome in. "
                         "<a href='/'>Ask the Jury &rarr;</a></p></div>"),
                    headers={"Set-Cookie":
                             f"jury_session={token}; Path=/; HttpOnly; "
                             f"SameSite=Lax"})
            return self.send_html(self.login_page(
                "That passcode did not match. Please try again — or check "
                "with Sayed if you are stuck."))
        if not self.authed():
            return self.send_json({"error": "Please enter the passcode first."}, 401)
        if u.path == "/api/ask":
            try:
                question = (json.loads(raw or b"{}").get("question") or "").strip()
            except Exception:
                question = ""
            if not question:
                return self.send_json({"error": "Type a question first."})
            with JOBS_LOCK:
                active = [j for j in JOBS.values() if j["status"] == "running"]
                if active:
                    return self.send_json(
                        {"job_id": active[0]["id"],
                         "note": "A question is already with the jury — "
                                 "one at a time, so here is its progress."})
                job_id = hashlib.sha256(
                    f"{time.time()}-{question}".encode()).hexdigest()[:12]
                JOBS[job_id] = {"id": job_id, "status": "queued",
                                "stage": "Asking the five…",
                                "started": time.time(), "run_id": None,
                                "error": None}
            threading.Thread(target=run_job, args=(job_id, question),
                             daemon=True).start()
            return self.send_json({"job_id": job_id})
        if u.path == "/api/intake":
            try:
                question = (json.loads(raw or b"{}").get("question") or "").strip()
            except Exception:
                question = ""
            if not question:
                return self.send_json({"error": "Type a question first."})
            with JOBS_LOCK:
                active = [j for j in INTAKE_JOBS.values()
                          if j["status"] == "running"]
                if active:
                    return self.send_json(
                        {"job_id": active[0]["id"],
                         "note": "An intake assessment is already "
                                 "running — one at a time, so here is "
                                 "its progress."})
                job_id = hashlib.sha256(
                    f"intake-{time.time()}-{question}".encode()).hexdigest()[:12]
                INTAKE_JOBS[job_id] = {"id": job_id, "status": "queued",
                                       "stage": "Intake is assessing…",
                                       "started": time.time(),
                                       "intake_id": None, "error": None}
            threading.Thread(target=run_intake_job, args=(job_id, question),
                             daemon=True).start()
            return self.send_json({"job_id": job_id})
        return self.send_json({"error": "Not found."}, 404)


def main():
    if not PASSCODE:
        print("WARNING: JURY_APP_PASSCODE is not set — the passcode gate "
              "is DISABLED.", file=sys.stderr)
    print(f"Jury of Five app: http://{HOST}:{PORT}  "
          f"(engine: {' '.join(resolve_engine_cmd())}, "
          f"mock={is_mock_mode()})", file=sys.stderr)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
