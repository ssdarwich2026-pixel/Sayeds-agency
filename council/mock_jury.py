#!/usr/bin/env python3
"""MOCK Jury of Five — a soft-pass mimic of jury.py for build & UI testing.

Same CLI as the real engine:
    python3 mock_jury.py run "<question>"
    python3 mock_jury.py probe

Differences from the real jury.py:
  - Instant, offline, $0. Makes NO network calls and uses NO free-request budget.
  - Run logs are written to council/mock-runs/ (never council/runs/), and the file,
    the header, and every answer are clearly labeled MOCK.
  - Output format is IDENTICAL to jury.py's run logs (same sections, same order),
    so the app can be built and tested against realistic verdicts.

App contract: point the app's engine command at this file for demo/test mode
(e.g. JURY_ENGINE_CMD="python3 council/mock_jury.py"), at jury.py for live use.
"""
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_RUNS = os.path.join(HERE, "mock-runs")

SEATS = [
    ("Advisor A", "nvidia/nemotron-3-ultra-550b-a55b:free",
     "NVIDIA, strategy & hard reasoning"),
    ("Advisor B", "google/gemma-4-31b-it:free", "Google, research breadth"),
    ("Advisor C", "xingchen-agi/xing4.0-29b-a4b:free", "Xingchen AGI, fresh eyes"),
    ("Advisor D", "dots-studio/dots-3-note-preview:free",
     "Dots Studio, structured general chat"),
    ("Advisor E", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
     "NVIDIA, dedicated reasoning"),
]

ANSWERS = [
    ("Start with the cheapest reversible step that produces real evidence within "
     "one week; measure it before committing anything bigger.",
     "Reversible steps cap the downside while still producing signal. Evidence "
     "beats opinion at this scale, and a one-week loop keeps momentum.",
     "Committing to the full plan before any evidence exists."),
    ("Talk to the five people closest to the problem first and mirror their "
     "exact words back in the offer; proximity beats polish.",
     "The nearest audience converts fastest and tells you the language that "
     "works, which then scales to colder audiences.",
     "Building in isolation and launching to silence."),
    ("Pick the option a competitor would find embarrassing to copy — the "
     "distinctive angle is the moat at this size.",
     "Small players win on distinctiveness, not budget. A copyable offer "
     "competes on price, which is a losing game at $0 spend.",
     "Blending in with a generic version of what already exists."),
    ("Write the plan as three dated checkpoints with a kill criterion on the "
     "first one; proceed only if the criterion is met.",
     "Structure turns a vague intention into a decision machine. The kill "
     "criterion protects the budget and the calendar.",
     "Letting the project drift without a decision date."),
    ("Do the manual, unscalable version first for ten users; automate only "
     "what repeats.",
     "Manual-first surfaces the real friction. Automation before repetition "
     "is guesswork with extra steps.",
     "Automating a process nobody has validated yet."),
]

ESCALATE_WORDS = ("launch", "invest", "contract", "hire", "loan", "legal", "$")


def slugify(q):
    keep = [c if c.isalnum() else "-" for c in q.lower()]
    s = "".join(keep)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:40] or "question"


def run(question):
    now = datetime.now()
    lines = []
    lines.append("# Jury of Five — run log [MOCK]")
    lines.append(f"- When: {now.strftime('%Y-%m-%d %H:%M:%S')} (local)")
    lines.append(f"- Question: {question}")
    lines.append("- Judge: nvidia/nemotron-3-ultra-550b-a55b:free [MOCK]")
    lines.append("- OpenRouter requests used: 0 (MOCK — no live calls)")
    lines.append("")
    lines.append("## The five answers")
    lines.append("")
    for (seat, model, note), (rec, why, risk) in zip(SEATS, ANSWERS):
        lines.append(f"### {seat} — {model} ({note}) [MOCK]")
        lines.append("")
        lines.append(f"**Recommendation:** {rec}")
        lines.append("")
        lines.append(f"**Reasoning:** {why}")
        lines.append("")
        lines.append(f"**Biggest Risk to Avoid:** {risk}")
        lines.append("")
    escalate = any(w in question.lower() for w in ESCALATE_WORDS)
    lines.append("## Verdict")
    lines.append("")
    lines.append("## VERDICT")
    lines.append(
        "Start with the cheapest reversible step that produces real evidence "
        f"within one week on this question — \"{question}\" Get the plan down "
        "as three dated checkpoints with a kill criterion on the first, take "
        "the manual version to the ten nearest people first, and let their "
        "response (in their words) decide the next move. Distinctiveness is "
        "the moat at this scale; evidence is the compass. [MOCK VERDICT — "
        "shape is real, content is canned for build testing.]")
    lines.append("")
    lines.append("## WHERE THE FIVE DISAGREED")
    lines.append(
        "**Sequencing:** Advisors A and E put evidence-gathering first; "
        "Advisor B would start with audience conversations before any step "
        "at all. The council sides with A/E: conversations are step one's "
        "raw material, not a prerequisite phase.\n\n"
        "**Risk posture:** Advisor C optimizes for distinctiveness even at "
        "the cost of speed; Advisor D optimizes for decision hygiene. Both "
        "are honored: the checkpoints carry the kill criterion, and the "
        "angle chosen inside them must be the embarrassing-to-copy one.")
    lines.append("")
    lines.append("## CONFIDENCE")
    lines.append(
        "Moderate-High (mock). The five agree on evidence-first sequencing; "
        "the open variable is execution speed, which the checkpoints police.")
    lines.append("")
    lines.append("## ESCALATION")
    if escalate:
        lines.append(
            "ESCALATION: YES — this question touches money, contracts, or a "
            "launch, which are In-Depth Crew triggers.\n\n"
            "ESCALATION PACKET [MOCK]\n"
            f"- Refined question: {question} — with budget ceiling, deadline, "
            "and downside cap stated explicitly.\n"
            "- What the Five established: evidence-first sequencing; kill "
            "criterion required before any spend.\n"
            "- Open disagreements: distinctiveness vs. speed (unresolved — "
            "needs market data).\n"
            "- Asked of the Crew: full department pass (strategy, creative, "
            "legal/IP, market, money) before commitment.")
    else:
        lines.append(
            "ESCALATION: NO. Tactical question, no money or legal risk, and "
            "the disagreements resolve into a single sequenced plan.")
    lines.append("")
    text = "\n".join(lines)
    os.makedirs(MOCK_RUNS, exist_ok=True)
    fname = f"{now.strftime('%Y-%m-%d-%H%M%S')}-MOCK-{slugify(question)}.md"
    path = os.path.join(MOCK_RUNS, fname)
    with open(path, "w") as f:
        f.write(text)
    print(text)
    print(f"Run log: {path}")
    print("OpenRouter requests used this run: 0 (MOCK)")
    return 0


def probe():
    for seat, model, note in SEATS:
        print(f"seat     {model}: OK (MOCK — no live call)  [{seat}, {note}]")
    print("Requests used: 0 (MOCK)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "probe":
        sys.exit(probe())
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        sys.exit(run(" ".join(sys.argv[2:])))
    print(__doc__)
    sys.exit(2)
