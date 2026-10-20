#!/usr/bin/env python3
"""Local free-call budget tracker — STANDALONE (Model 2) fallback.

Used only when the Muse connector budget tool named in config.yaml
(openrouter.budget_py) does not exist on this machine — i.e. when the
jury runs outside Muse. Mirrors that tool's CLI and output exactly:

  local_budget.py status    -> prints used/remaining for today
  local_budget.py check N   -> exit 0 if N calls fit, exit 1 if not
  local_budget.py record    -> record one call

State: .budget-local.json next to this file (gitignored), keyed by date.
Daily cap matches the connector tool: 50 free requests/day.
"""
import datetime
import json
import os
import sys

STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".budget-local.json")
DAILY_BUDGET = 50


def today():
    return datetime.datetime.now().isoformat()[:10]


def load():
    try:
        s = json.load(open(STATE))
    except (FileNotFoundError, json.JSONDecodeError):
        s = {}
    if s.get("date") != today():
        s = {"date": today(), "used": 0}
    return s


def save(s):
    json.dump(s, open(STATE, "w"))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    s = load()
    used, remaining = s["used"], DAILY_BUDGET - s["used"]
    if cmd == "status":
        print(f"date={s['date']} used={used} remaining={remaining} "
              f"budget={DAILY_BUDGET}")
        return 0
    if cmd == "record":
        s["used"] += 1
        save(s)
        return 0
    if cmd == "check":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        if n <= remaining:
            print(f"OK: {n} calls fit ({remaining} remaining)")
            return 0
        print(f"REFUSED: {n} calls requested, {remaining} remaining — "
              f"shrink the fan-out or wait for reset", file=sys.stderr)
        return 1
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
