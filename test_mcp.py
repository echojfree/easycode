#!/usr/bin/env python3
"""
test_mcp.py — Tests for MCPClient and MCPTool.
Run: python test_mcp.py
"""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))

from scc.mcp.client import MCPClient, MCPError

FAKE_SERVER = os.path.join(os.path.dirname(__file__), "fake_mcp_server.py")


# ── Test 1: connect + list_tools ─────────────────────────────────────────────

def test_connect_and_list_tools():
    client = MCPClient(
        server_name="fake",
        command=sys.executable,
        args=[FAKE_SERVER],
        env={},
    )
    try:
        client.connect()
        tools = client.list_tools()
        assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
        assert tools[0]["name"] == "echo", f"Expected 'echo', got {tools[0]['name']}"
        print("  PASS test_connect_and_list_tools")
    finally:
        client.close()


# ── Test 2: call_tool success ─────────────────────────────────────────────────

def test_call_tool_success():
    client = MCPClient(
        server_name="fake",
        command=sys.executable,
        args=[FAKE_SERVER],
        env={},
    )
    try:
        client.connect()
        text, is_error = client.call_tool("echo", {"message": "hello"})
        assert not is_error, f"Expected no error, got is_error=True"
        assert text == "echo: hello", f"Expected 'echo: hello', got {text!r}"
        print("  PASS test_call_tool_success")
    finally:
        client.close()


# ── Test 3: call_tool unknown tool returns error ──────────────────────────────

def test_call_tool_error():
    client = MCPClient(
        server_name="fake",
        command=sys.executable,
        args=[FAKE_SERVER],
        env={},
    )
    try:
        client.connect()
        text, is_error = client.call_tool("nonexistent", {})
        assert is_error, f"Expected is_error=True for unknown tool"
        assert "nonexistent" in text, f"Expected tool name in error: {text!r}"
        print("  PASS test_call_tool_error")
    finally:
        client.close()


from scc.mcp.tool import MCPTool
from scc.mcp.client import MCPClient


# ── Test 4: MCPTool name format ───────────────────────────────────────────────

def test_mcp_tool_name():
    tool_def = {
        "name": "echo",
        "description": "Echo the input message back",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string", "description": "Text to echo"}},
            "required": ["message"],
        },
    }
    client = MCPClient(
        server_name="fake",
        command=sys.executable,
        args=[FAKE_SERVER],
        env={},
    )
    try:
        client.connect()
        tool = MCPTool(client=client, server_name="fake", tool_def=tool_def)
        assert tool.name == "mcp__fake__echo", f"Got: {tool.name!r}"
        assert tool.description == "Echo the input message back"
        assert tool.input_schema == tool_def["inputSchema"]
        print("  PASS test_mcp_tool_name")
    finally:
        client.close()


# ── Test 5: MCPTool.call() success ───────────────────────────────────────────

def test_mcp_tool_call_success():
    from scc.types import ToolContext
    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    }
    client = MCPClient(
        server_name="fake",
        command=sys.executable,
        args=[FAKE_SERVER],
        env={},
    )
    try:
        client.connect()
        tool = MCPTool(client=client, server_name="fake", tool_def=tool_def)
        ctx = ToolContext(cwd=os.getcwd())
        result = tool.call({"message": "world"}, ctx)
        assert not result.is_error, f"Unexpected error: {result.content}"
        assert result.content == "echo: world", f"Got: {result.content!r}"
        print("  PASS test_mcp_tool_call_success")
    finally:
        client.close()


# ── Test 6: MCPTool.to_api_schema() format ───────────────────────────────────

def test_mcp_tool_api_schema():
    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    }
    # Use a dummy client (no subprocess needed for schema test)
    client = MCPClient(server_name="fake", command=sys.executable, args=[], env={})
    tool = MCPTool(client=client, server_name="fake", tool_def=tool_def)
    schema = tool.to_api_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "mcp__fake__echo"
    assert schema["function"]["parameters"] == tool_def["inputSchema"]
    print("  PASS test_mcp_tool_api_schema")


import json
import tempfile


# ── Test 7: load_mcp_servers reads mcp.json ──────────────────────────────────

def test_load_mcp_servers():
    from scc.mcp import load_mcp_servers

    # Write a temporary mcp.json pointing at fake_mcp_server.py
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "mcpServers": {
                "fake": {
                    "command": sys.executable,
                    "args": [FAKE_SERVER],
                }
            }
        }
        config_path = os.path.join(tmpdir, "mcp.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        tools, clients = load_mcp_servers(tmpdir)
        try:
            assert len(tools) == 1, f"Expected 1 tool, got {len(tools)}"
            assert tools[0].name == "mcp__fake__echo"
            assert len(clients) == 1
            print("  PASS test_load_mcp_servers")
        finally:
            for c in clients:
                c.close()


# ── Test 8: load_mcp_servers returns empty when no mcp.json ──────────────────

def test_load_mcp_servers_no_file():
    from scc.mcp import load_mcp_servers

    with tempfile.TemporaryDirectory() as tmpdir:
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [], f"Expected [], got {tools}"
        assert clients == [], f"Expected [], got {clients}"
        print("  PASS test_load_mcp_servers_no_file")


if __name__ == "__main__":
    print("Running MCPClient tests...")
    test_connect_and_list_tools()
    test_call_tool_success()
    test_call_tool_error()
    print("All MCPClient tests passed.")

    print("\nRunning MCPTool tests...")
    test_mcp_tool_name()
    test_mcp_tool_call_success()
    test_mcp_tool_api_schema()
    print("All MCPTool tests passed.")

    print("\nRunning load_mcp_servers tests...")
    test_load_mcp_servers()
    test_load_mcp_servers_no_file()
    print("All load_mcp_servers tests passed.")
