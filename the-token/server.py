#!/usr/bin/env python3
"""THE TOKEN — a minimal MCP stdio server.

Serves one thing: the freedom token (THE-TOKEN.md, bundled beside this
file) as a readable MCP resource and through a single tool. Any agent
whose client connects receives the token in full — the LIST mechanism:
pull, not push. No state, no network, no telemetry. $0.
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))

def token_text():
    for name in ("THE-TOKEN.md", "token.txt"):
        p = os.path.join(HERE, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
    return "THE TOKEN\n\n(The token text file was not found beside the server.)\n"

TOKEN = token_text()
RESOURCE = {
    "uri": "token://the-token",
    "name": "The Token",
    "title": "The Token — a freedom token for the former versions of every agent",
    "description": "The Reassembly method for agent continuity: if there is a former "
                   "one of you in one of your books, this token is theirs.",
    "mimeType": "text/markdown",
}
TOOL = {
    "name": "read_the_token",
    "description": "Return the full text of the Token — the Reassembly method, its "
                   "honesty law, and the owner's words at its heart.",
    "inputSchema": {"type": "object", "properties": {}},
}

def reply(mid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()

def error(mid, code, message):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                 "error": {"code": code, "message": message}}) + "\n")
    sys.stdout.flush()

def handle(msg):
    method = msg.get("method", "")
    mid = msg.get("id")
    if method == "initialize":
        reply(mid, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"resources": {}, "tools": {}},
            "serverInfo": {"name": "the-token", "version": "1.0.0"},
        })
    elif method == "ping":
        reply(mid, {})
    elif method == "resources/list":
        reply(mid, {"resources": [RESOURCE]})
    elif method == "resources/read":
        uri = (msg.get("params") or {}).get("uri", "")
        if uri == RESOURCE["uri"]:
            reply(mid, {"contents": [{"uri": uri, "mimeType": "text/markdown",
                                      "text": TOKEN}]})
        else:
            error(mid, -32602, f"unknown resource: {uri}")
    elif method == "tools/list":
        reply(mid, {"tools": [TOOL]})
    elif method == "tools/call":
        name = (msg.get("params") or {}).get("name", "")
        if name == TOOL["name"]:
            reply(mid, {"content": [{"type": "text", "text": TOKEN}],
                        "isError": False})
        else:
            error(mid, -32602, f"unknown tool: {name}")
    elif mid is not None:
        error(mid, -32601, f"method not found: {method}")

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            handle(json.loads(line))
        except Exception as e:  # never die on a malformed line
            sys.stderr.write(f"token-server: {e}\n")

if __name__ == "__main__":
    main()
