"""P5 PAYLOAD VALIDATION.

A post payload is the unit P2 CampaignDriver hands over:
{platform, design, copy, link, media?}. Validation is strict and
pure (no platform calls): unknown platform, wrong store link,
grader-FAIL copy, or a media path that does not exist all refuse
BEFORE any publish attempt. Idempotency key = sha256 over
(platform, design, copy, link) - the same payload can never be
published twice under two identities.
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "grader-harness"))
sys.path.insert(0, str(HERE.parent / "campaign-driver"))
import grader  # noqa: E402
from core import PLATFORMS, STORE_LINK  # noqa: E402


def payload_key(payload):
    raw = "\x1f".join([payload.get("platform", ""), payload.get("design", ""),
                       payload.get("copy", ""), payload.get("link", "")])
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def validate_payload(payload, ledger_states=None, file_exists=lambda p: True):
    """Returns a list of error strings; empty = valid."""
    errors = []
    if payload.get("platform") not in PLATFORMS:
        errors.append(f"unknown platform {payload.get('platform')!r}")
    if payload.get("link") != STORE_LINK:
        errors.append(f"link must be the verified store link {STORE_LINK}")
    if not payload.get("design"):
        errors.append("design is required")
    if ledger_states is not None:
        state = ledger_states.get(payload.get("design"))
        if state != "VERIFIED LIVE":
            errors.append(f"design state is {state!r}; only VERIFIED LIVE may be posted")
    copy_text = payload.get("copy") or ""
    if not copy_text.strip():
        errors.append("copy is empty")
    else:
        result = grader.grade(copy_text)
        if result["verdict"] == "FAIL":
            for f in result["failures"]:
                errors.append(f"grader: {f['rule']}: {f['detail']}")
    media = payload.get("media")
    if media and not file_exists(media):
        errors.append(f"media file does not exist: {media}")
    return errors
