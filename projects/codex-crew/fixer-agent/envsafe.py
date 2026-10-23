"""Environment sanitizer — design rule 3 (SPEC.md).

This VM's injected NO_PROXY carries IPv6 entries ([::1], fd8b:...::1)
that LiteLLM/httpx mis-parse ("Invalid port: ':1]'"), killing any
LLM call before it starts (proven in the 2026-10-23 cage test: the
error vanished once the entries were stripped). Every subprocess and
HTTP call the fixer spawns runs under a sanitized environment.
"""
import os

_IPV6_MARKERS = ("::", "[")


def _clean_no_proxy(value):
    if not value:
        return value
    kept = []
    for entry in value.split(","):
        e = entry.strip()
        if not e:
            continue
        if any(m in e for m in _IPV6_MARKERS):
            continue  # IPv6 entries are the parse hazard; drop them
        kept.append(e)
    return ",".join(kept)


def sanitize_env(env=None):
    """Return a copy of env with IPv6 NO_PROXY entries stripped."""
    out = dict(os.environ if env is None else env)
    for key in ("NO_PROXY", "no_proxy"):
        if key in out:
            out[key] = _clean_no_proxy(out[key])
    return out


def hazards(env=None):
    """List the entries sanitize_env would remove (for reports)."""
    src = os.environ if env is None else env
    found = []
    for key in ("NO_PROXY", "no_proxy"):
        for entry in (src.get(key) or "").split(","):
            e = entry.strip()
            if e and any(m in e for m in _IPV6_MARKERS):
                found.append(f"{key}: {e}")
    return found
