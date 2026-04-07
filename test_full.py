#!/usr/bin/env python3
"""
test_full.py — Comprehensive system tests for scc + MCP support.
Run: python test_full.py

Covers:
  1. MCP edge cases (malformed config, bad command, server crash, no tools)
  2. Built-in tool regression (read, write, edit, glob, grep, bash)
  3. Tool registry (TOOL_REGISTRY contents, get_tools, get_api_schemas)
  4. QueryEngine unit (init, _find_tool, clear, extra_tools wiring)
  5. Integration (load_mcp_servers → QueryEngine → _find_tool)
"""

from __future__ import annotations
import json
import os
import sys
import tempfile
import textwrap

sys.path.insert(0, os.path.dirname(__file__))

FAKE_SERVER = os.path.join(os.path.dirname(__file__), "fake_mcp_server.py")

_pass = 0
_fail = 0


def ok(name: str) -> None:
    global _pass
    _pass += 1
    print(f"  PASS {name}")


def fail(name: str, msg: str) -> None:
    global _fail
    _fail += 1
    print(f"  FAIL {name}: {msg}")


def section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ═══════════════════════════════════════════════════════════════
#  1. MCP edge cases
# ═══════════════════════════════════════════════════════════════

section("1. MCP edge cases")


def test_mcp_bad_command():
    """MCPClient raises MCPError for non-existent command."""
    from scc.mcp.client import MCPClient, MCPError
    client = MCPClient(server_name="bad", command="nonexistent_cmd_xyz", args=[], env={})
    try:
        client.connect()
        fail("test_mcp_bad_command", "Should have raised MCPError")
    except MCPError as e:
        assert "bad" in str(e) or "nonexistent" in str(e).lower() or "Cannot start" in str(e), \
            f"Error message unhelpful: {e}"
        ok("test_mcp_bad_command")
    except Exception as e:
        fail("test_mcp_bad_command", f"Wrong exception type {type(e).__name__}: {e}")


def test_mcp_server_crash_during_recv():
    """MCPClient raises MCPError when server process exits unexpectedly."""
    import subprocess
    # A server that immediately exits without sending any JSON
    crash_script = textwrap.dedent("""\
        import sys
        sys.exit(0)
    """)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(crash_script)
        crash_path = f.name
    try:
        from scc.mcp.client import MCPClient, MCPError
        client = MCPClient(server_name="crash", command=sys.executable,
                           args=[crash_path], env={})
        try:
            client.connect(timeout=3.0)
            fail("test_mcp_server_crash_during_recv", "Should have raised MCPError")
        except MCPError as e:
            ok("test_mcp_server_crash_during_recv")
        except Exception as e:
            fail("test_mcp_server_crash_during_recv", f"Wrong exception {type(e).__name__}: {e}")
    finally:
        os.unlink(crash_path)


def test_mcp_server_timeout():
    """MCPClient raises MCPError on timeout (server never responds)."""
    hang_script = textwrap.dedent("""\
        import time
        time.sleep(60)
    """)
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(hang_script)
        hang_path = f.name
    try:
        from scc.mcp.client import MCPClient, MCPError
        client = MCPClient(server_name="hang", command=sys.executable,
                           args=[hang_path], env={})
        try:
            client.connect(timeout=1.5)
            fail("test_mcp_server_timeout", "Should have raised MCPError")
        except MCPError as e:
            assert "Timeout" in str(e) or "timeout" in str(e).lower(), \
                f"Expected timeout message: {e}"
            ok("test_mcp_server_timeout")
        except Exception as e:
            fail("test_mcp_server_timeout", f"Wrong exception {type(e).__name__}: {e}")
    finally:
        os.unlink(hang_path)


def test_load_mcp_servers_malformed_json():
    """load_mcp_servers handles invalid JSON gracefully."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            f.write("{ not valid json }")
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == [], f"Expected empty, got tools={tools}"
        ok("test_load_mcp_servers_malformed_json")


def test_load_mcp_servers_not_a_dict():
    """load_mcp_servers handles non-dict JSON root gracefully."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump([1, 2, 3], f)
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == [], f"Expected empty, got tools={tools}"
        ok("test_load_mcp_servers_not_a_dict")


def test_load_mcp_servers_missing_command():
    """load_mcp_servers skips server entries with no command field."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"mcpServers": {"nocommand": {"args": []}}}
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump(config, f)
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == [], f"Expected empty, got tools={tools}"
        ok("test_load_mcp_servers_missing_command")


def test_load_mcp_servers_bad_server_cfg():
    """load_mcp_servers skips server entry if config is not a dict."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"mcpServers": {"badcfg": "not_a_dict"}}
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump(config, f)
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == [], f"Expected empty, got tools={tools}"
        ok("test_load_mcp_servers_bad_server_cfg")


def test_load_mcp_servers_bad_command_graceful():
    """load_mcp_servers skips failing servers without crashing."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "mcpServers": {
                "bad_server": {"command": "nonexistent_cmd_xyz", "args": []},
                "good_server": {"command": sys.executable, "args": [FAKE_SERVER]},
            }
        }
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump(config, f)
        tools, clients = load_mcp_servers(tmpdir)
        try:
            assert len(tools) == 1, f"Expected 1 tool from good_server, got {len(tools)}"
            assert tools[0].name == "mcp__good_server__echo"
            assert len(clients) == 1
            ok("test_load_mcp_servers_bad_command_graceful")
        finally:
            for c in clients:
                c.close()


def test_load_mcp_servers_empty_mcpServers():
    """load_mcp_servers returns empty for empty mcpServers dict."""
    from scc.mcp import load_mcp_servers
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"mcpServers": {}}
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump(config, f)
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == []
        ok("test_load_mcp_servers_empty_mcpServers")


def test_mcp_close_idempotent():
    """MCPClient.close() can be called multiple times safely."""
    from scc.mcp.client import MCPClient
    client = MCPClient(server_name="fake", command=sys.executable,
                       args=[FAKE_SERVER], env={})
    client.connect()
    client.close()
    client.close()  # second call should not raise
    ok("test_mcp_close_idempotent")


def test_mcp_close_before_connect():
    """MCPClient.close() before connect() is a no-op."""
    from scc.mcp.client import MCPClient
    client = MCPClient(server_name="fake", command=sys.executable,
                       args=[FAKE_SERVER], env={})
    client.close()  # must not raise
    ok("test_mcp_close_before_connect")


# ═══════════════════════════════════════════════════════════════
#  2. Built-in tool regression
# ═══════════════════════════════════════════════════════════════

section("2. Built-in tool regression")


def _make_ctx(tmpdir: str):
    from scc.types import ToolContext
    return ToolContext(cwd=tmpdir)


def test_file_write_then_read():
    from scc.tools.file_write_tool import FileWriteTool
    from scc.tools.file_read_tool import FileReadTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        path = os.path.join(tmpdir, "hello.txt")
        w = FileWriteTool()
        result = w.call({"file_path": path, "content": "hello world"}, ctx)
        assert not result.is_error, f"write error: {result.content}"

        r = FileReadTool()
        result2 = r.call({"file_path": path}, ctx)
        assert not result2.is_error, f"read error: {result2.content}"
        assert "hello world" in result2.content, f"Content missing: {result2.content}"
        ok("test_file_write_then_read")


def test_file_edit():
    from scc.tools.file_write_tool import FileWriteTool
    from scc.tools.file_edit_tool import FileEditTool
    from scc.tools.file_read_tool import FileReadTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        path = os.path.join(tmpdir, "edit.txt")
        FileWriteTool().call({"file_path": path, "content": "foo bar baz"}, ctx)

        e = FileEditTool()
        result = e.call({"file_path": path, "old_string": "bar", "new_string": "qux"}, ctx)
        assert not result.is_error, f"edit error: {result.content}"

        content = FileReadTool().call({"file_path": path}, ctx).content
        assert "qux" in content, f"Edit not applied: {content}"
        assert "bar" not in content, f"Old string still present: {content}"
        ok("test_file_edit")


def test_file_edit_not_found_string():
    from scc.tools.file_write_tool import FileWriteTool
    from scc.tools.file_edit_tool import FileEditTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        path = os.path.join(tmpdir, "x.txt")
        FileWriteTool().call({"file_path": path, "content": "abc"}, ctx)
        result = FileEditTool().call(
            {"file_path": path, "old_string": "xyz", "new_string": "---"}, ctx
        )
        assert result.is_error, "Expected error when old_string not found"
        ok("test_file_edit_not_found_string")


def test_glob_tool():
    from scc.tools.glob_tool import GlobTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        # Create some files
        for name in ["a.py", "b.py", "c.txt"]:
            open(os.path.join(tmpdir, name), "w").close()
        result = GlobTool().call({"pattern": "*.py", "path": tmpdir}, ctx)
        assert not result.is_error, f"glob error: {result.content}"
        assert "a.py" in result.content
        assert "b.py" in result.content
        assert "c.txt" not in result.content
        ok("test_glob_tool")


def test_grep_tool():
    from scc.tools.file_write_tool import FileWriteTool
    from scc.tools.grep_tool import GrepTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        path = os.path.join(tmpdir, "search.txt")
        FileWriteTool().call({
            "file_path": path,
            "content": "line one\nfind me here\nline three"
        }, ctx)
        result = GrepTool().call({"pattern": "find me", "path": tmpdir}, ctx)
        assert not result.is_error, f"grep error: {result.content}"
        assert "find me" in result.content
        ok("test_grep_tool")


def test_bash_tool():
    from scc.tools.bash_tool import BashTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = BashTool().call({"command": "echo hello_bash_test"}, ctx)
        assert not result.is_error, f"bash error: {result.content}"
        assert "hello_bash_test" in result.content
        ok("test_bash_tool")


def test_file_read_missing():
    from scc.tools.file_read_tool import FileReadTool
    with tempfile.TemporaryDirectory() as tmpdir:
        ctx = _make_ctx(tmpdir)
        result = FileReadTool().call({"file_path": os.path.join(tmpdir, "no_such.txt")}, ctx)
        assert result.is_error, "Should be error for missing file"
        ok("test_file_read_missing")


# ═══════════════════════════════════════════════════════════════
#  3. Tool registry
# ═══════════════════════════════════════════════════════════════

section("3. Tool registry")


def test_tool_registry_contents():
    from scc.tools import TOOL_REGISTRY
    expected = {"bash", "read_file", "write_file", "edit_file", "glob", "grep"}
    actual = set(TOOL_REGISTRY.keys())
    missing = expected - actual
    assert not missing, f"Missing tools in TOOL_REGISTRY: {missing}"
    ok("test_tool_registry_contents")


def test_get_tools_no_extra():
    from scc.tools import get_tools
    tools = get_tools()
    names = {t.name for t in tools}
    assert "bash" in names
    assert "read_file" in names
    ok("test_get_tools_no_extra")


def test_get_api_schemas_no_extra():
    from scc.tools import get_api_schemas
    schemas = get_api_schemas()
    assert all(isinstance(s, dict) for s in schemas)
    assert all(s.get("type") == "function" for s in schemas)
    assert all("name" in s.get("function", {}) for s in schemas)
    ok("test_get_api_schemas_no_extra")


def test_get_tools_with_extra():
    """get_tools(extra=[...]) appends extra tools."""
    from scc.mcp.client import MCPClient
    from scc.mcp.tool import MCPTool
    from scc.tools import get_tools

    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    dummy_client = MCPClient(server_name="t", command=sys.executable, args=[], env={})
    mcp_tool = MCPTool(client=dummy_client, server_name="t", tool_def=tool_def)

    tools = get_tools(extra=[mcp_tool])
    names = [t.name for t in tools]
    assert "mcp__t__echo" in names, f"MCP tool not in list: {names}"
    assert "bash" in names  # built-in still there
    ok("test_get_tools_with_extra")


def test_get_api_schemas_with_extra():
    """get_api_schemas(extra=[...]) includes MCP tool schema."""
    from scc.mcp.client import MCPClient
    from scc.mcp.tool import MCPTool
    from scc.tools import get_api_schemas

    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    dummy_client = MCPClient(server_name="t2", command=sys.executable, args=[], env={})
    mcp_tool = MCPTool(client=dummy_client, server_name="t2", tool_def=tool_def)

    schemas = get_api_schemas(extra=[mcp_tool])
    names = [s["function"]["name"] for s in schemas]
    assert "mcp__t2__echo" in names
    ok("test_get_api_schemas_with_extra")


# ═══════════════════════════════════════════════════════════════
#  4. QueryEngine unit tests
# ═══════════════════════════════════════════════════════════════

section("4. QueryEngine unit tests")


def _make_engine(extra_tools=None):
    from scc.agent import QueryEngine
    # Use a dummy OllamaClient — we won't actually call it in unit tests
    class FakeClient:
        model = "test-model"
        def chat(self, messages, tools): raise RuntimeError("Should not call chat in unit tests")
    return QueryEngine(client=FakeClient(), extra_tools=extra_tools)


def test_queryengine_init():
    engine = _make_engine()
    assert engine.messages == []
    assert engine.turn_count == 0
    ok("test_queryengine_init")


def test_queryengine_clear():
    from scc.types import make_user_msg
    engine = _make_engine()
    engine.messages.append(make_user_msg("hello"))
    assert engine.turn_count == 1
    engine.clear()
    assert engine.messages == []
    assert engine.turn_count == 0
    ok("test_queryengine_clear")


def test_queryengine_find_builtin_tool():
    engine = _make_engine()
    tool = engine._find_tool("bash")
    assert tool is not None, "bash tool not found"
    assert tool.name == "bash"
    ok("test_queryengine_find_builtin_tool")


def test_queryengine_find_unknown_tool():
    engine = _make_engine()
    tool = engine._find_tool("nonexistent_tool_xyz")
    assert tool is None
    ok("test_queryengine_find_unknown_tool")


def test_queryengine_extra_tools_wired():
    """MCP tools passed as extra_tools are findable via _find_tool."""
    from scc.mcp.client import MCPClient
    from scc.mcp.tool import MCPTool

    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    dummy_client = MCPClient(server_name="srv", command=sys.executable, args=[], env={})
    mcp_tool = MCPTool(client=dummy_client, server_name="srv", tool_def=tool_def)

    engine = _make_engine(extra_tools=[mcp_tool])

    found = engine._find_tool("mcp__srv__echo")
    assert found is not None, "MCP tool not found via _find_tool"
    assert found.name == "mcp__srv__echo"
    ok("test_queryengine_extra_tools_wired")


def test_queryengine_extra_tools_in_schemas():
    """MCP tools appear in tool schemas sent to LLM."""
    from scc.mcp.client import MCPClient
    from scc.mcp.tool import MCPTool

    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    dummy_client = MCPClient(server_name="srv2", command=sys.executable, args=[], env={})
    mcp_tool = MCPTool(client=dummy_client, server_name="srv2", tool_def=tool_def)

    engine = _make_engine(extra_tools=[mcp_tool])
    names = [s["function"]["name"] for s in engine._tool_schemas]
    assert "mcp__srv2__echo" in names
    ok("test_queryengine_extra_tools_in_schemas")


def test_queryengine_execute_tool_unknown():
    """_execute_tool returns error ToolResult for unknown tool name."""
    from scc.types import ToolResult
    engine = _make_engine()
    result = engine._execute_tool(None, {"name": "ghost"})
    assert result.is_error
    assert "Unknown tool" in result.content
    ok("test_queryengine_execute_tool_unknown")


def test_queryengine_execute_builtin_bash():
    """_execute_tool can execute bash echo command."""
    engine = _make_engine()
    tool = engine._find_tool("bash")
    result = engine._execute_tool(tool, {"command": "echo qengine_test"})
    assert not result.is_error, f"bash failed: {result.content}"
    assert "qengine_test" in result.content
    ok("test_queryengine_execute_builtin_bash")


# ═══════════════════════════════════════════════════════════════
#  5. Integration: load_mcp_servers → QueryEngine → tool call
# ═══════════════════════════════════════════════════════════════

section("5. Integration: load_mcp_servers → QueryEngine")


def test_integration_mcp_tool_execution():
    """
    Full integration: load MCP server from mcp.json → QueryEngine →
    _find_tool → _execute_tool → real subprocess call.
    """
    from scc.mcp import load_mcp_servers

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "mcpServers": {
                "fake": {
                    "command": sys.executable,
                    "args": [FAKE_SERVER],
                }
            }
        }
        with open(os.path.join(tmpdir, "mcp.json"), "w") as f:
            json.dump(config, f)

        tools, clients = load_mcp_servers(tmpdir)
        try:
            assert len(tools) == 1
            engine = _make_engine(extra_tools=tools)

            # Find the MCP tool
            tool = engine._find_tool("mcp__fake__echo")
            assert tool is not None, "MCP tool not found in engine"

            # Execute it
            result = engine._execute_tool(tool, {"message": "integration_test"})
            assert not result.is_error, f"Tool execution error: {result.content}"
            assert "integration_test" in result.content, f"Got: {result.content!r}"
            ok("test_integration_mcp_tool_execution")
        finally:
            for c in clients:
                c.close()


def test_integration_no_mcp_json():
    """
    With no mcp.json, load_mcp_servers returns empty lists,
    and QueryEngine still initialises normally with built-in tools only.
    """
    from scc.mcp import load_mcp_servers

    with tempfile.TemporaryDirectory() as tmpdir:
        tools, clients = load_mcp_servers(tmpdir)
        assert tools == [] and clients == []

        engine = _make_engine(extra_tools=tools)
        assert engine._find_tool("bash") is not None
        assert engine._find_tool("mcp__fake__echo") is None
        ok("test_integration_no_mcp_json")


def test_integration_mcp_context_isolated():
    """
    Each QueryEngine has its own _extra_registry; MCP tools in one engine
    don't bleed into another.
    """
    from scc.mcp.client import MCPClient
    from scc.mcp.tool import MCPTool

    tool_def = {
        "name": "echo",
        "description": "Echo",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }
    dummy_client = MCPClient(server_name="iso", command=sys.executable, args=[], env={})
    mcp_tool = MCPTool(client=dummy_client, server_name="iso", tool_def=tool_def)

    engine_a = _make_engine(extra_tools=[mcp_tool])
    engine_b = _make_engine(extra_tools=[])

    assert engine_a._find_tool("mcp__iso__echo") is not None
    assert engine_b._find_tool("mcp__iso__echo") is None
    ok("test_integration_mcp_context_isolated")


# ═══════════════════════════════════════════════════════════════
#  6. Tool validate_input
# ═══════════════════════════════════════════════════════════════

section("6. Tool validate_input")


def test_validate_input_base_always_ok():
    from scc.tools.bash_tool import BashTool
    tool = BashTool()
    ok_result, err = tool.validate_input({"command": "ls"})
    assert ok_result is True and err == ""
    ok("test_validate_input_base_always_ok")


def test_to_api_schema_structure():
    """Every built-in tool produces a valid to_api_schema() result."""
    from scc.tools import get_tools
    for tool in get_tools():
        schema = tool.to_api_schema()
        assert schema["type"] == "function", f"{tool.name}: missing type"
        fn = schema["function"]
        assert "name" in fn, f"{tool.name}: missing name"
        assert "description" in fn, f"{tool.name}: missing description"
        assert "parameters" in fn, f"{tool.name}: missing parameters"
    ok("test_to_api_schema_structure")


# ═══════════════════════════════════════════════════════════════
#  Run all tests
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Section 1
    test_mcp_bad_command()
    test_mcp_server_crash_during_recv()
    test_mcp_server_timeout()
    test_load_mcp_servers_malformed_json()
    test_load_mcp_servers_not_a_dict()
    test_load_mcp_servers_missing_command()
    test_load_mcp_servers_bad_server_cfg()
    test_load_mcp_servers_bad_command_graceful()
    test_load_mcp_servers_empty_mcpServers()
    test_mcp_close_idempotent()
    test_mcp_close_before_connect()

    # Section 2
    test_file_write_then_read()
    test_file_edit()
    test_file_edit_not_found_string()
    test_glob_tool()
    test_grep_tool()
    test_bash_tool()
    test_file_read_missing()

    # Section 3
    test_tool_registry_contents()
    test_get_tools_no_extra()
    test_get_api_schemas_no_extra()
    test_get_tools_with_extra()
    test_get_api_schemas_with_extra()

    # Section 4
    test_queryengine_init()
    test_queryengine_clear()
    test_queryengine_find_builtin_tool()
    test_queryengine_find_unknown_tool()
    test_queryengine_extra_tools_wired()
    test_queryengine_extra_tools_in_schemas()
    test_queryengine_execute_tool_unknown()
    test_queryengine_execute_builtin_bash()

    # Section 5
    test_integration_mcp_tool_execution()
    test_integration_no_mcp_json()
    test_integration_mcp_context_isolated()

    # Section 6
    test_validate_input_base_always_ok()
    test_to_api_schema_structure()

    print(f"\n{'═'*60}")
    print(f"  Results: {_pass} passed, {_fail} failed")
    print(f"{'═'*60}")
    sys.exit(0 if _fail == 0 else 1)
