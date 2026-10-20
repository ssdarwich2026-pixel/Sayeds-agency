#!/usr/bin/env python3
"""Jury of Five — Room 1 web app.

A single stdlib http.server service that wraps council/jury.py (or the
mock engine) so one non-technical user can ask questions and read verdicts
from a phone. No dependencies, no database, no build step.

Env vars:
  JURY_APP_PASSCODE  If set, a passcode gate protects the app (form + cookie).
                     If unset, the gate is DISABLED and a warning is shown.
  JURY_ENGINE_CMD    Engine command, e.g. "python3 council/mock_jury.py".
                     Default: "python3 council/jury.py".
  JURY_APP_MOCK      If "1", use council/mock_jury.py (unless JURY_ENGINE_CMD
                     is set explicitly).
  JURY_APP_PORT      Port to listen on. Default 8765. On this standalone
                     branch, the host-provided PORT env var (e.g. Render)
                     takes precedence when set: PORT -> JURY_APP_PORT -> 8765.
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

PASSCODE = os.environ.get("JURY_APP_PASSCODE", "")
# STANDALONE (Model 2): cloud hosts inject PORT; it wins over JURY_APP_PORT.
PORT = int(os.environ.get("PORT") or os.environ.get("JURY_APP_PORT")
           or "8765")
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
    cannot be read, returns a plain-language 'unavailable' line.

    STANDALONE (Model 2): if the connector tool's path does not exist on
    this machine, fall back to council/local_budget.py, which keeps the
    same 50/day count in council/.budget-local.json (its `status` output
    is identical, and the engine records against the same file)."""
    try:
        with open(CONFIG_PATH) as f:
            m = re.search(r"budget_py:\s*(\S+)", f.read())
        if not m:
            return None
        budget_py = m.group(1)
        if not os.path.exists(budget_py):
            local = os.path.join(COUNCIL_DIR, "local_budget.py")
            if os.path.exists(local):
                budget_py = local
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
            body = ("<div class='card'><h2 style='margin-top:0'>Jury of 45+</h2>"
                    "<p><strong>In the works.</strong></p>"
                    "<p>The In-Depth Crew — the full 45-model deep review — "
                    "is being built. When a Jury of Five verdict says "
                    "&ldquo;escalate&rdquo;, its packet will go here.</p></div>")
            return self.send_html(page("Jury of 45+", body, "room2"))
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
