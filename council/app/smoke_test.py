#!/usr/bin/env python3
"""Smoke test for the Jury of Five app — mock engine only, $0, offline.

Boots the app on a scratch port with a test passcode, then checks:
  1. Passcode gate: unauthenticated request gets the login page; wrong
     passcode gets a plain-language refusal; right passcode gets in.
  2. Ask page serves with title, budget line, textarea, Ask button.
  3. Room 2 tab ("Jury of 45+") shows the placeholder.
  4. Mock Ask (a launch/contract question, to trigger escalation) ->
     poll job -> verdict page has ALL sections: agreed answer, who
     answered, juror answers, disagreements, confidence, escalation
     packet in a copyable box.
  5. History lists existing runs (including the mock run just made and
     the pre-existing real runs) and a history verdict opens.

Run:  python3 council/app/smoke_test.py
Exit code 0 = PASS.
"""
import http.cookiejar
import os
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(APP_DIR, "server.py")
PASSCODE = "smoke-test-passcode"
FAILURES = []


def check(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    env = dict(os.environ, JURY_APP_PORT=str(port), JURY_APP_HOST="127.0.0.1",
               JURY_APP_PASSCODE=PASSCODE, JURY_APP_MOCK="1")
    env.pop("JURY_ENGINE_CMD", None)
    env.pop("PORT", None)  # standalone branch: PORT would override the above
    proc = subprocess.Popen([sys.executable, SERVER], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

        def get(path, op=None):
            with (op or opener).open(base + path, timeout=15) as r:
                return r.read().decode()

        def post(path, data, ctype="application/x-www-form-urlencoded"):
            req = urllib.request.Request(
                base + path, data=data,
                headers={"Content-Type": ctype}, method="POST")
            with opener.open(req, timeout=15) as r:
                return r.read().decode()

        # wait for boot
        for _ in range(50):
            try:
                get("/", urllib.request.build_opener())
                break
            except Exception:
                time.sleep(0.2)
        else:
            check("app boots", False, "server did not respond")
            return 1
        check("app boots", True)

        # 1. passcode gate
        anon = urllib.request.build_opener()
        login_page = get("/", anon)
        check("unauthenticated request gets passcode page",
              "Enter the passcode" in login_page)
        wrong = post("/login", urllib.parse.urlencode(
            {"passcode": "definitely-wrong"}).encode())
        check("wrong passcode refused in plain language",
              "did not match" in wrong)
        post("/login", urllib.parse.urlencode({"passcode": PASSCODE}).encode())

        # 2. ask page
        home = get("/")
        check("ask page has title", "Jury of Five" in home)
        check("ask page has budget line (real or unavailable, never fake)",
              "free-request budget" in home)
        check("ask page has textarea + Ask button",
              "<textarea" in home and "Ask the Jury" in home)

        # 3. room 2
        room2 = get("/room2")
        check("Jury of 45+ tab shows placeholder",
              "Jury of 45+" in room2 and "In the works" in room2)

        # 4. mock ask -> poll -> verdict (launch/contract -> escalation YES)
        import json
        resp = post("/api/ask", json.dumps(
            {"question": "Should we sign a contract and launch the shirt "
                         "this week?"}).encode(), "application/json")
        job_id = json.loads(resp)["job_id"]
        run_id = None
        for _ in range(60):
            with opener.open(base + f"/api/job/{job_id}", timeout=15) as r:
                job = json.loads(r.read().decode())
            if job["status"] == "done":
                run_id = job["run_id"]
                break
            if job["status"] == "error":
                break
            time.sleep(0.5)
        check("mock ask job completes", run_id is not None, str(job))
        verdict = get("/verdict?f=" + urllib.parse.quote(run_id or ""))
        check("verdict shows agreed answer first/large",
              "answer" in verdict and "cheapest reversible step" in verdict)
        check("verdict shows who answered", "Who answered" in verdict
              and "jurors answered" in verdict)
        check("verdict shows juror answers (collapsible)",
              "<details>" in verdict and "Advisor A" in verdict)
        check("verdict shows disagreements",
              "Where the five disagreed" in verdict)
        check("verdict shows confidence",
              "Confidence" in verdict and "Moderate-High" in verdict)
        check("verdict shows escalation packet in copyable box",
              "ESCALATION PACKET" in verdict and "copybox" in verdict)

        # 5. history
        hist = get("/history")
        check("history lists the mock run just made",
              "sign a contract and launch the shirt" in hist)
        check("history lists pre-existing real runs",
              "print-on-demand shirt" in hist)
        first = get("/verdict?f=" + urllib.parse.quote(
            "runs/2026-10-20-101024-for-a-print-on-demand-shirt.md"))
        check("history verdict opens read-only with sections",
              "Where the five disagreed" in first and "Confidence" in first)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    if FAILURES:
        print(f"\nSMOKE TEST FAILED: {len(FAILURES)} check(s): {FAILURES}")
        return 1
    print("\nSMOKE TEST PASSED — all checks green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
