#!/usr/bin/env python3
"""
One poll cycle across Sayed's HQ groups. Designed for cron, every 5 minutes:

    */5 * * * * cd /opt/sayeds-agency/integrations/groupme-bot && /usr/bin/python3 poll_once.py >> poll.log 2>&1

Exit codes: 0 = the cycle completed (zero new messages is normal, not a
failure); 1 = something failed (bad config, network down, a group
errored). Set MAILTO in the crontab and cron emails you on every
nonzero exit — that's the dead-man's switch.

Config (environment, or a .env file next to this script):
  GROUPME_USER_TOKEN   OAuth token from dev.groupme.com/applications.
                       FULL-ACCOUNT credential: .env / GitHub Secrets only,
                       never chat, logs, or screenshots.
  GROUPS_JSON          Preferred: {"<group_id>": "<bot_id>", ...}
  GROUP_IDS            Alternative: "123,456" — every group shares ...
  GROUPME_BOT_ID       ... this one bot_id (the single-group case).
"""

import json
import os
import sys

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import Agent
from poll import MAX_REPLIES_PER_RUN, Poller


def die(message):
    print("ERROR: %s" % message, file=sys.stderr)
    sys.exit(1)


def load_groups():
    raw = os.environ.get("GROUPS_JSON", "").strip()
    if raw:
        try:
            mapping = json.loads(raw)
        except json.JSONDecodeError as exc:
            die("GROUPS_JSON is not valid JSON (%s)" % exc)
        if not isinstance(mapping, dict) or not mapping:
            die("GROUPS_JSON must be a non-empty object like {\"123\": \"botid\"}")
        groups = {}
        for gid, bot_id in mapping.items():
            if not str(gid).strip() or not str(bot_id).strip():
                die("GROUPS_JSON has an empty group_id or bot_id")
            groups[str(gid).strip()] = str(bot_id).strip()
        return groups
    gids = os.environ.get("GROUP_IDS", "").strip()
    bot_id = os.environ.get("GROUPME_BOT_ID", "").strip()
    if gids and bot_id:
        groups = {g.strip(): bot_id for g in gids.split(",") if g.strip()}
        if not groups:
            die("GROUP_IDS was set but contained no usable ids")
        return groups
    die(
        "no groups configured. Set GROUPS_JSON='{\"<group_id>\": \"<bot_id>\"}' "
        "or set both GROUP_IDS and GROUPME_BOT_ID."
    )


def main():
    token = os.environ.get("GROUPME_USER_TOKEN", "").strip()
    if not token:
        die(
            "GROUPME_USER_TOKEN is not set. Get it at "
            "https://dev.groupme.com/applications (register app -> authorize "
            "-> copy the access_token) and put it in .env — never in chat."
        )
    groups = load_groups()

    agent = Agent()  # data dir defaults to ./data (or BOT_DATA_DIR)
    poller = Poller(user_token=token, agent=agent, data_dir=agent.data_dir)
    replies, errors = poller.poll_all(groups)

    print("poll cycle done: %d groups, %d replies" % (len(groups), replies))
    if errors:
        for gid, err in errors.items():
            print("group %s FAILED: %s" % (gid, err), file=sys.stderr)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
