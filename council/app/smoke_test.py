#!/usr/bin/env python3
"""Smoke test for the Jury of Five app — mock engine only, $0, offline.

Boots the app on a scratch port with a test passcode, then checks:
  1. Passcode gate: unauthenticated request gets the login page; wrong
     passcode gets a plain-language refusal; right passcode gets in.
  2. Ask page serves with title, budget line, textarea, Ask button.
  3. Room 2 tab ("Jury of 45+") shows the intake form (no placeholder).
  4. Mock Ask (a launch/contract question, to trigger escalation) ->
     poll job -> verdict page has ALL sections: agreed answer, who
     answered, juror answers, disagreements, confidence, escalation
     packet in a copyable box.
  5. History lists existing runs (including the mock run just made and
     the pre-existing real runs) and a history verdict opens.
  6. Room 2 intake (mock mode): a complex money/legal/launch question
     gets a high complexity score, routed departments (including Legal /
     IP and Money), and a time estimate; the result states the full run
     is NOT YET WIRED with a disabled Start button; a simple question
     scores lower (Simple band). Intake writes no jury run logs — it
     must never start, or fake, a full run.

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

        # 3. room 2 intake form
        room2 = get("/room2")
        check("Jury of 45+ tab shows intake form, not the placeholder",
              "Jury of 45+" in room2 and "Run intake assessment" in room2
              and "<textarea" in room2 and "In the works" not in room2)

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

        # 6. Room 2 intake (mock mode)
        council_dir = os.path.dirname(APP_DIR)
        runs_before = {d: sorted(os.listdir(os.path.join(council_dir, d)))
                       for d in ("runs", "mock-runs")
                       if os.path.isdir(os.path.join(council_dir, d))}
        mintake_dir = os.path.join(council_dir, "mock-intake-runs")
        mintake_before = (set(os.listdir(mintake_dir))
                          if os.path.isdir(mintake_dir) else set())

        def run_intake(question):
            resp = post("/api/intake", json.dumps(
                {"question": question}).encode(), "application/json")
            iid_job = json.loads(resp)["job_id"]
            for _ in range(60):
                with opener.open(base + f"/api/intake-job/{iid_job}",
                                 timeout=15) as r:
                    ijob = json.loads(r.read().decode())
                if ijob["status"] in ("done", "error"):
                    break
                time.sleep(0.5)
            return ijob

        complex_q = ("Should we sign a contract, spend money, and launch "
                     "a trademarked shirt design to a new market?")
        ijob = run_intake(complex_q)
        check("mock intake job completes",
              ijob.get("status") == "done" and bool(ijob.get("intake_id")),
              str(ijob))
        intake = get("/room2/intake?f=" + urllib.parse.quote(
            ijob.get("intake_id") or ""))
        import re as _re
        _sm = _re.search(r"(\d+) / 10", intake)
        check("intake shows complexity score and band",
              "Complexity" in intake and _sm is not None
              and int(_sm.group(1)) >= 7
              and ("(Complex)" in intake or "(Major)" in intake),
              f"score match: {_sm.group(0) if _sm else None}")
        check("intake routes to Legal / IP and Money departments",
              "Legal / IP" in intake and "Money" in intake)
        check("intake names routed departments section",
              "Departments it would route to" in intake
              and "Strategy" in intake and "Market" in intake)
        check("intake shows a time estimate for the full run",
              "Time estimate for the full run" in intake
              and ("minutes" in intake or "hour" in intake))
        check("intake states the full run is NOT YET WIRED",
              "NOT YET WIRED" in intake)
        check("intake Start full run button is disabled (no fake run)",
              "Start full run" in intake and "disabled" in intake)

        simple_job = run_intake("What colour should the team socks be?")
        simple = get("/room2/intake?f=" + urllib.parse.quote(
            simple_job.get("intake_id") or ""))
        check("simple question intake completes and scores Simple",
              simple_job.get("status") == "done" and "Simple" in simple)

        room2_after = get("/room2")
        check("room2 lists past intake assessments",
              "sign a contract, spend money" in room2_after)

        runs_after = {d: sorted(os.listdir(os.path.join(council_dir, d)))
                      for d in ("runs", "mock-runs")
                      if os.path.isdir(os.path.join(council_dir, d))}
        check("intake started no jury/full run (run logs unchanged)",
              runs_before == runs_after,
              f"before={runs_before} after={runs_after}")

        # tidy the mock intake logs this test created (repo hygiene;
        # mock jury runs keep the pre-existing smoke-test behaviour)
        if os.path.isdir(mintake_dir):
            for name in set(os.listdir(mintake_dir)) - mintake_before:
                os.remove(os.path.join(mintake_dir, name))
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
