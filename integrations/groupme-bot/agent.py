"""
Phase 1 brain: a tiny dispatcher with a skill registry.

Each skill is a plain function taking (argument, context) and returning a
reply string. To add a new skill: write the function, add one line to
SKILLS below — the `help` command picks it up automatically.

PHASE 2 NOTE (multi-model brains): this dispatcher is the seam where
LiteLLM / OpenRouter plugs in. The plan: instead of matching the first
word, send the message plus the skill list to a model, let the model pick
the skill and its arguments, then run the chosen skill exactly as below.
The skills themselves don't change — only the dispatcher gets smarter,
and each call can use a *different* model.
"""

import os
from datetime import datetime

# Where the bot keeps its notebooks. Overridable with BOT_DATA_DIR.
DATA_DIR = os.environ.get(
    "BOT_DATA_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"),
)


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def skill_help(argument, ctx):
    """Show what the bot can do."""
    lines = ["Here's what I can do (Phase 1 brain) — just type the command in the group:"]
    for name in sorted(SKILLS):
        lines.append(f"  • {name} — {SKILLS[name][1]}")
    lines.append("")
    lines.append("Phase 2 will let me understand plain sentences too, not just commands.")
    return "\n".join(lines)


def skill_status(argument, ctx):
    """Summarize the latest crew run results."""
    path = os.path.join(ctx["data_dir"], "crew-status.md")
    if not os.path.exists(path):
        return (
            "No crew status on file yet.\n\n"
            "Here's how this works: every time a crew finishes a run, it writes "
            "its latest result to crew-status.md, and I'll summarize it here when "
            "you ask for 'status'. The crews aren't wired to that file yet — "
            "that's coming with the Phase 1 repo scaffold."
        )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content if content else "The status file exists but is empty."


def skill_note(argument, ctx):
    """Jot down a timestamped note: note <text>"""
    if not argument:
        return "Usage: note <something to jot down>\nExample: note NFT prices locked at 0.05 ETH"
    line = f"[{_stamp()}] {argument}\n"
    with open(os.path.join(ctx["data_dir"], "notes.log"), "a", encoding="utf-8") as f:
        f.write(line)
    return "Noted. ✏️"


def skill_remember(argument, ctx):
    """Save a fact for later: remember <fact>"""
    if not argument:
        return "Usage: remember <fact worth keeping>\nExample: remember Alli is out of town Oct 17 week"
    line = f"- [{_stamp()}] {argument}\n"
    with open(os.path.join(ctx["data_dir"], "memory-scratch.md"), "a", encoding="utf-8") as f:
        f.write(line)
    return "Saved to memory. 🧠"


# name -> (handler function, one-line description for `help`)
SKILLS = {
    "help": (skill_help, "list everything I can do"),
    "status": (skill_status, "latest crew run results"),
    "note": (skill_note, "jot down a timestamped note — note <text>"),
    "remember": (skill_remember, "save a fact for later — remember <fact>"),
}


def is_known_command(text):
    """True if text invokes a registered skill.

    The poller uses this for first-run catch-up: pre-existing chatter gets
    marked seen without a reply, but real commands still get answered.
    """
    from webhook_logic import parse_command  # local import: no cycles, testable
    command, _ = parse_command(text)
    return command in SKILLS


class Agent:
    """The dispatcher. One instance lives for the whole server process."""

    def __init__(self, data_dir=None):
        self.data_dir = data_dir or DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)

    def handle(self, text, sender_name="there"):
        """Turn an incoming message into a reply string (or None = stay silent)."""
        from webhook_logic import parse_command  # local import: no cycles, testable

        command, argument = parse_command(text)
        if not command:
            return None
        entry = SKILLS.get(command)
        if entry is None:
            return (
                f"I don't know '{command}' yet, {sender_name}.\n"
                "Type 'help' to see what I can do."
            )
        handler, _ = entry
        ctx = {"data_dir": self.data_dir, "sender_name": sender_name}
        try:
            return handler(argument, ctx)
        except Exception as exc:  # never let a skill crash the webhook
            return f"That skill hit a snag: {exc}"
