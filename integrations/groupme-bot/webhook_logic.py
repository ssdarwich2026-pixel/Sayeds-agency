"""
Pure decision logic for the GroupMe webhook.

Kept in its own file (no FastAPI, no network) so it can be unit-tested
without installing anything or starting a server.
"""

# Bot-posted messages are capped at 1,000 characters (verified 2026-10-06),
# so we keep every outbound message comfortably under that. (GroupMe's web
# client separately chokes on ~3,000-char pastes — a different limit.)
MAX_MESSAGE_CHARS = 990


def should_respond(payload: dict) -> bool:
    """Decide whether an incoming GroupMe callback deserves a reply.

    Returns False (stay silent) when:
      - the message came from a bot (sender_type == "bot"). This is the
        SELF-REPLY GUARD: without it, the bot would answer its own
        messages forever, spamming the group in an infinite loop.
      - it is a system message (someone joined/left, group renamed, ...).
      - there is no text to react to (photo-only messages, likes, ...).
    """
    if not isinstance(payload, dict):
        return False
    if payload.get("sender_type") == "bot":
        return False
    if payload.get("system") is True:
        return False
    text = payload.get("text")
    if text is None or not str(text).strip():
        return False
    return True


def parse_command(text: str):
    """Split 'note buy milk tomorrow' -> ('note', 'buy milk tomorrow').

    Tolerates a leading '!' or '/' so '!help' and '/help' work too.
    Returns ('', '') for empty input.
    """
    text = str(text).strip() if text is not None else ""
    if not text:
        return "", ""
    parts = text.split(None, 1)
    command = parts[0].lower().lstrip("!/")
    argument = parts[1].strip() if len(parts) > 1 else ""
    return command, argument


def chunk_message(text: str, limit: int = MAX_MESSAGE_CHARS):
    """Split a long reply into GroupMe-safe chunks.

    Prefers to break on newlines; falls back to a hard cut. The chunks
    rejoin to the original text (minus the newlines we cut on).
    """
    text = str(text)
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
