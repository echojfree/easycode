# MCP Support Design — Simple Claude Code (scc)

**Date**: 2026-04-07
**Status**: Approved
**Scope**: Add stdio MCP server support to the `scc/` package

---

## 1. Background

The existing `scc/` implementation is a simplified Claude Code agent that supports 6 built-in tools (bash, read_file, write_file, edit_file, glob, grep). This spec adds support for MCP (Model Context Protocol) servers over stdio transport, allowing external tool servers to be registered and called transparently by the agent loop.

---

## 2. Goals

- Support any stdio MCP server defined in a project-level `mcp.json` file
- MCP tools appear alongside built-in tools in the agent loop — no special handling required
- Missing or broken MCP servers log a warning and are skipped; they do not crash startup
- Minimal changes to existing files

---

## 3. Non-Goals

- SSE / HTTP transport (stdio only)
- Global/user-level MCP config (project-level `mcp.json` only)
- MCP resources or prompts (tools only)
- Hot-reload of MCP servers during a session

---

## 4. Architecture

### 4.1 New files

```
scc/
  mcp/
    __init__.py       ← load_mcp_servers(cwd) → list[MCPTool]
    client.py         ← MCPClient: subprocess + JSON-RPC 2.0
    tool.py           ← MCPTool(Tool): wraps one MCP tool
```

### 4.2 Modified files (minimal)

| File | Change |
|------|--------|
| `scc/tools/__init__.py` | `get_tools(extra=[])` and `get_api_schemas(extra=[])` accept extra tools |
| `scc/agent.py` | `QueryEngine.__init__` accepts `extra_tools: list[Tool] = []` |
| `scc/cli.py` | `main()` calls `load_mcp_servers(cwd)`, passes result to `QueryEngine` |

### 4.3 Startup flow

```
main()
  → load_mcp_servers(cwd)
      reads mcp.json (missing → return [])
      for each server:
          MCPClient.connect()   # spawn subprocess + initialize handshake
          tools = client.list_tools()
          yield MCPTool(client, server_name, tool_def) for each tool
  → QueryEngine(client, cwd, extra_tools=mcp_tools)
      TOOL_REGISTRY merged with mcp_tools
  → repl()
  → on exit: client.close() for each MCPClient
```

---

## 5. MCPClient — Subprocess & JSON-RPC Transport

`MCPClient` owns one subprocess per MCP server. Communication uses newline-delimited JSON-RPC 2.0 over stdin/stdout (the MCP stdio transport spec).

### 5.1 API

```python
class MCPClient:
    def connect(self) -> None
        # Spawns subprocess, sends initialize, waits for initialized notification

    def list_tools(self) -> list[dict]
        # Sends tools/list, returns raw tool defs from server

    def call_tool(self, name: str, arguments: dict) -> tuple[str, bool]
        # Sends tools/call, returns (content_text, is_error)

    def close(self) -> None
        # Terminates subprocess gracefully
```

### 5.2 Wire format

Each message is one JSON line terminated by `\n`.

Request:
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"read_file","arguments":{"path":"/tmp/foo.txt"}}}
```

Success response:
```json
{"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"file contents..."}]}}
```

Content extraction: concatenate the `text` field of all `{"type":"text"}` blocks in `result.content`. Non-text blocks (images etc.) are ignored.

Error response:
```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32000,"message":"file not found"}}
```

### 5.3 Initialize handshake

```
→ {"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"scc","version":"0.1.0"}}}
← {"jsonrpc":"2.0","id":0,"result":{...}}
→ {"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
```

### 5.4 Timeouts

| Operation | Timeout |
|-----------|---------|
| initialize handshake | 5s |
| tools/list | 5s |
| tools/call | 30s |

### 5.5 Error handling

- Subprocess fails to start → log warning, skip server
- initialize / tools/list fails → log warning, skip server
- tools/call returns JSON-RPC error → `ToolResult(is_error=True, content=error.message)`
- tools/call timeout → `ToolResult(is_error=True, content="Tool call timed out")`

---

## 6. MCPTool — Tool Wrapper

```python
class MCPTool(Tool):
    name: str          # "mcp__<server_name>__<tool_name>"
    description: str   # from tools/list response
    input_schema: dict # from tools/list response
    is_read_only = False

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        text, is_error = self._client.call_tool(self._tool_name, input)
        return ToolResult(content=text, is_error=is_error)

    def render_use(self, input: dict) -> str:
        return f"[MCP:{self._server_name}] {self._tool_name}({input})"
```

Tool name format: `mcp__filesystem__read_file` — double underscores, matching Claude Code's convention.

---

## 7. Config Format

File: `mcp.json` in the working directory (project root).

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
      "env": {}
    },
    "my-server": {
      "command": "python",
      "args": ["my_mcp_server.py"]
    }
  }
}
```

Fields:
| Field | Required | Description |
|-------|----------|-------------|
| `command` | yes | Executable to spawn |
| `args` | no | Argument list (default `[]`) |
| `env` | no | Additional env vars merged into current env (default `{}`) |

If `mcp.json` does not exist, MCP support is silently disabled.

---

## 8. Integration Detail

### `scc/tools/__init__.py`
```python
def get_tools(extra: list[Tool] = []) -> list[Tool]:
    return list(TOOL_REGISTRY.values()) + extra

def get_api_schemas(extra: list[Tool] = []) -> list[dict]:
    return [t.to_api_schema() for t in get_tools(extra)]
```

### `scc/agent.py` — QueryEngine
```python
def __init__(self, client, cwd=None, extra_tools: list[Tool] = []):
    ...
    self._tool_schemas = get_api_schemas(extra=extra_tools)
    self._extra_registry = {t.name: t for t in extra_tools}

def _find_tool(self, name: str) -> Tool | None:
    return TOOL_REGISTRY.get(name) or self._extra_registry.get(name)
```

### `scc/cli.py` — main()
```python
mcp_tools, mcp_clients = load_mcp_servers(cwd)
engine = QueryEngine(client=client, cwd=cwd, extra_tools=mcp_tools)
try:
    repl(engine)
finally:
    for c in mcp_clients:
        c.close()
```

---

## 9. Testing

Manual smoke test with a real MCP server (e.g. `@modelcontextprotocol/server-filesystem`):

1. Create `mcp.json` pointing at the filesystem server
2. Run `python main.py`
3. Ask agent: "list files in /tmp using mcp tools"
4. Verify `mcp__filesystem__*` tools appear in tool call output

Unit-testable in isolation:
- `MCPClient` can be tested with a simple echo MCP server script
- `MCPTool.call()` can be tested by mocking `MCPClient.call_tool()`
