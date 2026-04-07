#!/usr/bin/env python3
"""
fake_mcp_server.py — Minimal stdio MCP server for testing.
Exposes one tool: echo(message) -> "echo: <message>"
"""
import sys
import json


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method = msg.get("method", "")
    msg_id = msg.get("id")

    # Notifications have no "id" — don't respond
    if msg_id is None:
        continue

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "serverInfo": {"name": "fake", "version": "0.1.0"},
        }})

    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": [
            {
                "name": "echo",
                "description": "Echo the input message back",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "Text to echo"},
                    },
                    "required": ["message"],
                },
            }
        ]}})

    elif method == "tools/call":
        tool_name = msg["params"]["name"]
        args = msg["params"]["arguments"]
        if tool_name == "echo":
            send({"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": [{"type": "text", "text": f"echo: {args.get('message', '')}"}],
            }})
        else:
            send({"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32601, "message": f"Unknown tool: {tool_name}",
            }})
