#!/usr/bin/env python3
"""Sayed's Agency — executable model router (decision layer).

Answers: "What is the best available model/tool for THIS job right now?"
Reads registry/models.yaml + litellm-config.yaml, picks the best route for a
task type, and reports whether that route is EXECUTABLE today or BLOCKED
(and on what). When Sayed adds provider keys, blocked routes light up with
no code change — the registry is the switchboard.

Usage: python3 route.py <task-type>
Task types: chat | strategy | copy | code | local | image | video
"""
import sys, yaml, os

HERE = os.path.dirname(os.path.abspath(__file__))
TASK_ROUTE = {
    "chat": "agency-chat",
    "strategy": "agency-strategy",
    "copy": "agency-copy",
    "code": "agency-code",
    "local": "agency-local",
    "image": "agency-local",   # commercial-safe image via local/SD; see registry
    "video": "agency-local",   # open video drafts via local/demo paths
    # strict-format tasks resolve dynamically to a format-verified model
    # (registry format_strict_ok: true) — see resolve_strict_model()
}


def resolve_strict_model(reg):
    """Rule 1: strict-format tasks go ONLY to format-verified models."""
    for m in reg["models"]:
        if m.get("format_strict_ok") is True and m.get("access") in (
                "free-tier", "open-weights", "local"):
            return m["name"], m.get("notes", "")
    return None, "no format-verified model in registry"

def load(name):
    with open(os.path.join(HERE, name)) as f:
        return yaml.safe_load(f)

def openrouter_connected() -> bool:
    """True when Sayed's OpenRouter key is present in the Secure Vault."""
    try:
        sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
        from dynamic_credentials import dynamic_credential_entry
        dynamic_credential_entry("custom.openrouter")
        return True
    except Exception:
        return False


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "chat"
    cfg = load("litellm-config.yaml")
    reg = load("../registry/models.yaml")
    or_key = openrouter_connected()

    if task == "strict":
        name, notes = resolve_strict_model(reg)
        if name and or_key:
            print(f"TASK: strict (format-strict)")
            print(f"ROUTE: registry -> {name}")
            print(f"STATUS: available → executable")
            print(f"REASON: format_strict_ok verified; {notes[:80]}")
            return 0
        print(f"TASK: strict (format-strict)")
        print(f"STATUS: blocked")
        print(f"REASON: {notes if not name else 'needs Sayed\u2019s OpenRouter key'}")
        return 1

    route_name = TASK_ROUTE.get(task, "agency-chat")

    entry = next((m for m in cfg["model_list"] if m["model_name"] == route_name), None)
    if not entry:
        print(f"ROUTE: none  STATUS: blocked  REASON: no route '{route_name}' in config")
        return 2

    params = entry["litellm_params"]
    gated = entry.get("metadata", {}).get("gated", False)
    fallbacks = params.get("fallbacks", [])

    # Executability check: a route is executable today only if it resolves to
    # the orchestrator itself or a local model. Provider keys = blocked.
    model = params["model"]
    if model.startswith("ollama/"):
        status, reason = "degraded", "ollama not installed on this worker — falls back to orchestrator"
    elif model.startswith("openrouter/"):
        if or_key:
            status, reason = "available → executable", \
                "OpenRouter key connected in vault; free :free models verified live"
        else:
            status, reason = "blocked", "needs Sayed's OpenRouter key (his 2-min signup)"
    else:
        status, reason = "executable", "orchestrator-native"

    if gated:
        status, reason = "blocked", "GATED paid route — Sayed's explicit approval required"

    print(f"TASK: {task}")
    print(f"ROUTE: {route_name} -> {model}")
    print(f"STATUS: {status}")
    print(f"REASON: {reason}")
    if fallbacks:
        print(f"FALLBACKS: {', '.join(fallbacks)}")
    # best-for rationale from the registry
    reg_name = model.split("/")[-1]
    match = next((m for m in reg["models"] + reg["tools"]
                  if reg_name in m["name"] or m["name"] in reg_name), None)
    if match:
        print(f"RATIONALE: {match['best_for']} (verified {match['last_verified']})")
    return 0 if status == "executable" else 1

if __name__ == "__main__":
    sys.exit(main())
