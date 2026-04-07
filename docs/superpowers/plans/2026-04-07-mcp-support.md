# MCP Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stdio MCP server support to the `scc/` package so MCP tools appear transparently in the agent loop alongside built-in tools.

**Architecture:** A new `scc/mcp/` sub-package owns subprocess lifecycle and JSON-RPC 2.0 transport (`client.py`), wraps each discovered tool as a `MCPTool(Tool)` subclass (`tool.py`), and exposes `load_mcp_servers(cwd)` (`__init__.py`). At startup `main()` calls `load_mcp_servers`, passes the resulting tools to `QueryEngine` as `extra_tools`, and closes the clients on exit. The agent loop requires no changes.

**Tech Stack:** Python stdlib only — `subprocess`, `threading`, `json`, `os`. No external MCP SDK.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `fake_mcp_server.py` | Minimal MCP server for testing (echo tool) |
| Create | `test_mcp.py` | Unit tests for MCPClient and MCPTool |
| Create | `scc/mcp/__init__.py` | `load_mcp_servers(cwd)` — reads `mcp.json`, spawns servers |
| Create | `scc/mcp/client.py` | `MCPClient` — subprocess lifecycle + JSON-RPC 2.0 |
| Create | `scc/mcp/tool.py` | `MCPTool(Tool)` — wraps one MCP tool |
| Modify | `scc/tools/__init__.py:45-61` | Add `extra` param to `get_tools()` and `get_api_schemas()` |
| Modify | `scc/agent.py:81-98,190` | Add `extra_tools` param, `_extra_registry`, `_find_tool()` |
| Modify | `scc/cli.py:204-216` | Call `load_mcp_servers`, pass to `QueryEngine`, cleanup on exit |

---

## Task 1: Create fake MCP server for testing

**Files:**
- Create: `fake_mcp_server.py`

- [ ] **Step 1: Write fake_mcp_server.py**

```python
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
```

- [ ] **Step 2: Verify the server speaks correctly**

```bash
echo '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | python fake_mcp_server.py
```

Expected output (one JSON line):
```
{"jsonrpc": "2.0", "id": 0, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "fake", "version": "0.1.0"}}}
```

- [ ] **Step 3: Commit**

```bash
git add fake_mcp_server.py
git commit -m "test: add fake MCP stdio server for testing"
```

---

## Task 2: Create scc/mcp/client.py (MCPClient)

**Files:**
- Create: `scc/mcp/client.py`
- Create: `scc/mcp/__init__.py` (empty package marker for now)

- [ ] **Step 1: Write the failing test in test_mcp.py**

```python
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


if __name__ == "__main__":
    print("Running MCPClient tests...")
    test_connect_and_list_tools()
    test_call_tool_success()
    test_call_tool_error()
    print("All MCPClient tests passed.")
```

- [ ] **Step 2: Run test to verify it fails (module not found)**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected: `ModuleNotFoundError: No module named 'scc.mcp.client'`

- [ ] **Step 3: Create empty package marker**

```python
# scc/mcp/__init__.py — populated in Task 4
```

- [ ] **Step 4: Write scc/mcp/client.py**

```python
"""
scc/mcp/client.py — MCP stdio transport client
===============================================
对应 Claude Code 源码:
  src/services/mcp/client.ts → MCPClient (stdio transport)

通信协议: JSON-RPC 2.0，每条消息一行 JSON（以 \\n 结尾），
通过子进程的 stdin/stdout 传输。
"""

from __future__ import annotations
import json
import os
import subprocess
import threading
from typing import Optional


class MCPError(Exception):
    """MCP 通信错误"""


class MCPClient:
    """
    管理单个 MCP 服务器的子进程生命周期和 JSON-RPC 通信。

    生命周期:
        client = MCPClient(...)
        client.connect()          # 启动子进程 + initialize 握手
        tools = client.list_tools()
        text, err = client.call_tool(name, args)
        client.close()            # 终止子进程
    """

    def __init__(
        self,
        server_name: str,
        command: str,
        args: list[str],
        env: dict[str, str],
    ) -> None:
        self.server_name = server_name
        self._command = command
        self._args = args
        self._env = env
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._next_id: int = 1   # id 0 is reserved for initialize

    # ── 连接（启动子进程 + initialize 握手）──────────────────────────────────

    def connect(self, timeout: float = 5.0) -> None:
        """
        启动服务器子进程并完成 MCP initialize 握手。
        失败时抛出 MCPError。
        """
        merged_env = {**os.environ, **self._env}
        try:
            self._proc = subprocess.Popen(
                [self._command] + self._args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=merged_env,
            )
        except FileNotFoundError as e:
            raise MCPError(f"Cannot start server '{self.server_name}': {e}") from e

        # → initialize
        self._send({
            "jsonrpc": "2.0",
            "id": 0,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "scc", "version": "0.1.0"},
            },
        })

        # ← initialize response
        resp = self._recv(timeout=timeout)
        if "error" in resp:
            raise MCPError(f"initialize failed: {resp['error'].get('message', resp['error'])}")

        # → notifications/initialized  (notification — no id, no response expected)
        self._send({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })

    # ── 工具发现 ──────────────────────────────────────────────────────────────

    def list_tools(self, timeout: float = 5.0) -> list[dict]:
        """
        发送 tools/list，返回原始工具定义列表。
        每个工具定义包含 name, description, inputSchema。
        """
        resp = self._request("tools/list", {}, timeout=timeout)
        if "error" in resp:
            raise MCPError(f"tools/list failed: {resp['error'].get('message', resp['error'])}")
        return resp.get("result", {}).get("tools", [])

    # ── 工具调用 ──────────────────────────────────────────────────────────────

    def call_tool(
        self,
        name: str,
        arguments: dict,
        timeout: float = 30.0,
    ) -> tuple[str, bool]:
        """
        调用 MCP 工具，返回 (content_text, is_error)。

        content_text: result.content 中所有 type=text 块的文本拼接。
        is_error: True 表示 JSON-RPC error 或 result.isError=True。
        """
        resp = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=timeout,
        )

        if "error" in resp:
            msg = resp["error"].get("message", str(resp["error"]))
            return msg, True

        result = resp.get("result", {})
        content_blocks = result.get("content", [])
        text = "\n".join(
            block["text"]
            for block in content_blocks
            if block.get("type") == "text"
        )
        is_error = bool(result.get("isError", False))
        return text, is_error

    # ── 关闭 ──────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """终止子进程。"""
        if self._proc is None:
            return
        try:
            self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=3)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    # ── 内部：JSON-RPC 发送 / 接收 ────────────────────────────────────────────

    def _request(self, method: str, params: dict, timeout: float) -> dict:
        """发送请求并等待响应（持有锁，单线程安全）。"""
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            self._send({
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            })
            return self._recv(timeout=timeout)

    def _send(self, obj: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise MCPError("Not connected")
        data = (json.dumps(obj) + "\n").encode("utf-8")
        self._proc.stdin.write(data)
        self._proc.stdin.flush()

    def _recv(self, timeout: float) -> dict:
        """
        从 stdout 读取一条 JSON-RPC 响应（跳过通知消息）。
        使用守护线程实现跨平台超时（Windows 不支持 select on pipes）。
        """
        result: list[Optional[dict]] = [None]
        error: list[Optional[Exception]] = [None]

        def _read() -> None:
            try:
                while True:
                    if self._proc is None or self._proc.stdout is None:
                        error[0] = MCPError("Server process gone")
                        return
                    line = self._proc.stdout.readline()
                    if not line:
                        error[0] = MCPError("Server closed stdout")
                        return
                    text = line.decode("utf-8").strip()
                    if not text:
                        continue
                    obj = json.loads(text)
                    # Skip notifications (they have no "id")
                    if "id" not in obj:
                        continue
                    result[0] = obj
                    return
            except Exception as exc:
                error[0] = exc

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            raise MCPError(f"Timeout ({timeout}s) waiting for response from '{self.server_name}'")
        if error[0] is not None:
            raise error[0]  # type: ignore[misc]
        return result[0]  # type: ignore[return-value]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected:
```
Running MCPClient tests...
  PASS test_connect_and_list_tools
  PASS test_call_tool_success
  PASS test_call_tool_error
All MCPClient tests passed.
```

- [ ] **Step 6: Commit**

```bash
git add scc/mcp/__init__.py scc/mcp/client.py test_mcp.py
git commit -m "feat: add MCPClient with stdio JSON-RPC transport"
```

---

## Task 3: Create scc/mcp/tool.py (MCPTool)

**Files:**
- Create: `scc/mcp/tool.py`
- Modify: `test_mcp.py` — append MCPTool tests

- [ ] **Step 1: Append MCPTool tests to test_mcp.py**

Add after the existing MCPClient tests (before `if __name__ == "__main__":`):

```python
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
```

Also update the `__main__` block at the bottom of `test_mcp.py` to call the new tests:

```python
if __name__ == "__main__":
    print("Running MCPClient tests...")
    test_connect_and_list_tools()
    test_call_tool_success()
    test_call_tool_error()
    print("All MCPClient tests passed.\n")

    print("Running MCPTool tests...")
    test_mcp_tool_name()
    test_mcp_tool_call_success()
    test_mcp_tool_api_schema()
    print("All MCPTool tests passed.")
```

- [ ] **Step 2: Run tests to verify MCPTool tests fail**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected: `ModuleNotFoundError: No module named 'scc.mcp.tool'`

- [ ] **Step 3: Write scc/mcp/tool.py**

```python
"""
scc/mcp/tool.py — MCPTool: wraps one MCP tool as a Tool subclass
=================================================================
对应 Claude Code 源码:
  src/services/mcp/client.ts → MCPTool (adapts MCP tool to Tool interface)

工具命名约定: mcp__<server_name>__<tool_name>
（双下划线，与 Claude Code 保持一致）
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from ..tool import Tool
from ..types import ToolContext, ToolResult

if TYPE_CHECKING:
    from .client import MCPClient


class MCPTool(Tool):
    """
    将 MCP 服务器的单个工具包装为 Tool 子类实例。

    name        = "mcp__<server_name>__<tool_name>"
    description = 来自 tools/list 响应
    input_schema= 来自 tools/list 响应（JSON Schema）
    """

    def __init__(
        self,
        client: "MCPClient",
        server_name: str,
        tool_def: dict,
    ) -> None:
        self._client = client
        self._server_name = server_name
        self._tool_name = tool_def["name"]

        # Instance attributes override any class-level annotations from Tool
        self.name: str = f"mcp__{server_name}__{self._tool_name}"
        self.description: str = tool_def.get("description", "")
        self.input_schema: dict = tool_def.get("inputSchema", {"type": "object", "properties": {}})
        self.is_read_only: bool = False

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        text, is_error = self._client.call_tool(
            name=self._tool_name,
            arguments=input,
        )
        return ToolResult(content=text, is_error=is_error)

    def render_use(self, input: dict) -> str:
        return f"[MCP:{self._server_name}] {self._tool_name}({input})"
```

- [ ] **Step 4: Run tests to verify all pass**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected:
```
Running MCPClient tests...
  PASS test_connect_and_list_tools
  PASS test_call_tool_success
  PASS test_call_tool_error
All MCPClient tests passed.

Running MCPTool tests...
  PASS test_mcp_tool_name
  PASS test_mcp_tool_call_success
  PASS test_mcp_tool_api_schema
All MCPTool tests passed.
```

- [ ] **Step 5: Commit**

```bash
git add scc/mcp/tool.py test_mcp.py
git commit -m "feat: add MCPTool wrapper and tests"
```

---

## Task 4: Create scc/mcp/__init__.py (load_mcp_servers)

**Files:**
- Modify: `scc/mcp/__init__.py` (replace placeholder)

- [ ] **Step 1: Write scc/mcp/__init__.py**

```python
"""
scc/mcp/__init__.py — MCP 服务器加载入口
=========================================
对应 Claude Code 源码:
  src/services/mcp/ → MCPServerManager / assembleToolPool MCP 部分

load_mcp_servers(cwd) 读取 mcp.json，启动所有配置的服务器，
返回 (tools, clients) 供 QueryEngine 和 CLI 使用。
"""

from __future__ import annotations
import json
import os

from .client import MCPClient, MCPError
from .tool import MCPTool


def load_mcp_servers(cwd: str) -> tuple[list[MCPTool], list[MCPClient]]:
    """
    读取 <cwd>/mcp.json，为每个服务器启动子进程并发现工具。

    返回 (mcp_tools, mcp_clients):
      - mcp_tools:   所有成功加载的 MCPTool 实例（传给 QueryEngine）
      - mcp_clients: 所有活跃的 MCPClient 实例（程序退出时调用 close()）

    如果 mcp.json 不存在，静默返回 ([], [])。
    服务器启动失败时打印警告并跳过，不影响其他服务器。
    """
    config_path = os.path.join(cwd, "mcp.json")
    if not os.path.exists(config_path):
        return [], []

    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARNING: Cannot read mcp.json: {e}")
        return [], []

    servers: dict = config.get("mcpServers", {})
    if not servers:
        return [], []

    all_tools: list[MCPTool] = []
    all_clients: list[MCPClient] = []

    for server_name, server_cfg in servers.items():
        command: str = server_cfg.get("command", "")
        args: list[str] = server_cfg.get("args", [])
        env: dict[str, str] = server_cfg.get("env", {})

        if not command:
            print(f"  WARNING: MCP server '{server_name}' has no 'command', skipping.")
            continue

        client = MCPClient(server_name=server_name, command=command, args=args, env=env)
        try:
            client.connect()
            raw_tools = client.list_tools()
            server_tools = [
                MCPTool(client=client, server_name=server_name, tool_def=td)
                for td in raw_tools
            ]
            all_tools.extend(server_tools)
            all_clients.append(client)
            print(f"  MCP '{server_name}': {len(server_tools)} tool(s) loaded")
        except (MCPError, Exception) as e:
            print(f"  WARNING: MCP server '{server_name}' failed: {e}")
            try:
                client.close()
            except Exception:
                pass

    return all_tools, all_clients


__all__ = ["load_mcp_servers", "MCPClient", "MCPTool", "MCPError"]
```

- [ ] **Step 2: Write a quick load test in test_mcp.py — append after existing tests**

Add to `test_mcp.py` (before the `__main__` block):

```python
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
```

Update `__main__` block:

```python
if __name__ == "__main__":
    print("Running MCPClient tests...")
    test_connect_and_list_tools()
    test_call_tool_success()
    test_call_tool_error()
    print("All MCPClient tests passed.\n")

    print("Running MCPTool tests...")
    test_mcp_tool_name()
    test_mcp_tool_call_success()
    test_mcp_tool_api_schema()
    print("All MCPTool tests passed.\n")

    print("Running load_mcp_servers tests...")
    test_load_mcp_servers()
    test_load_mcp_servers_no_file()
    print("All load_mcp_servers tests passed.")
```

- [ ] **Step 3: Run all tests**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected: all 8 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add scc/mcp/__init__.py test_mcp.py
git commit -m "feat: add load_mcp_servers with mcp.json config support"
```

---

## Task 5: Modify scc/tools/__init__.py — accept extra tools

**Files:**
- Modify: `scc/tools/__init__.py:45-61`

- [ ] **Step 1: Update get_tools and get_api_schemas to accept extra param**

In `scc/tools/__init__.py`, replace:

```python
def get_tools() -> list[Tool]:
    """
    返回所有可用工具列表。
    对应 Claude Code: getTools(permissionContext)

    Claude Code 会根据权限模式（plan/bypassPermissions）过滤，
    这里始终返回全部工具（简化版不做权限控制）。
    """
    return list(_ALL_TOOLS)


def get_api_schemas() -> list[dict]:
    """
    返回工具的 API Schema 列表，用于发送给 LLM。
    对应 Claude Code: tools.map(t => toolToAPISchema(t))
    """
    return [t.to_api_schema() for t in _ALL_TOOLS]
```

With:

```python
def get_tools(extra: list[Tool] | None = None) -> list[Tool]:
    """
    返回所有可用工具列表（含 MCP 工具）。
    对应 Claude Code: getTools(permissionContext) + assembleToolPool() MCP 部分

    extra: 额外工具列表（如 MCP 工具），追加到内置工具之后。
    """
    return list(_ALL_TOOLS) + (list(extra) if extra else [])


def get_api_schemas(extra: list[Tool] | None = None) -> list[dict]:
    """
    返回工具的 API Schema 列表，用于发送给 LLM。
    对应 Claude Code: tools.map(t => toolToAPISchema(t))

    extra: 额外工具列表（如 MCP 工具）。
    """
    return [t.to_api_schema() for t in get_tools(extra)]
```

- [ ] **Step 2: Verify existing code still works (no regressions)**

```bash
cd F:/code/easycode && python -c "from scc.tools import get_tools, get_api_schemas; print(len(get_tools()), 'tools'); print(len(get_api_schemas()), 'schemas')"
```

Expected:
```
6 tools
6 schemas
```

- [ ] **Step 3: Commit**

```bash
git add scc/tools/__init__.py
git commit -m "feat: allow extra tools in get_tools and get_api_schemas"
```

---

## Task 6: Modify scc/agent.py — add extra_tools support

**Files:**
- Modify: `scc/agent.py:81-98` (`__init__`)
- Modify: `scc/agent.py:190` (`find_tool` call in `_query_loop`)

- [ ] **Step 1: Update QueryEngine.__init__ to accept extra_tools**

In `scc/agent.py`, replace:

```python
    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        cwd: Optional[str] = None,
    ):
        self.client = client or OllamaClient()
        self.cwd    = cwd or os.getcwd()

        # 对应 Claude Code: QueryEngine.mutableMessages
        # 存储完整对话历史（不含 system prompt）
        self.messages: list[dict] = []

        # 工具 API Schema（缓存，不每次重新生成）
        self._tool_schemas = get_api_schemas()

        # 当前的 ToolContext（每次 submit_message 时更新 messages）
        self._context = ToolContext(cwd=self.cwd, messages=self.messages)
```

With:

```python
    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        cwd: Optional[str] = None,
        extra_tools: Optional[list] = None,
    ):
        self.client = client or OllamaClient()
        self.cwd    = cwd or os.getcwd()

        # 对应 Claude Code: QueryEngine.mutableMessages
        # 存储完整对话历史（不含 system prompt）
        self.messages: list[dict] = []

        # MCP 工具注册表（name → Tool），与内置工具分开存储
        self._extra_registry: dict[str, object] = {
            t.name: t for t in (extra_tools or [])
        }

        # 工具 API Schema（缓存，包含 MCP 工具）
        self._tool_schemas = get_api_schemas(extra=extra_tools or [])

        # 当前的 ToolContext（每次 submit_message 时更新 messages）
        self._context = ToolContext(cwd=self.cwd, messages=self.messages)
```

- [ ] **Step 2: Replace find_tool call with self._find_tool in _query_loop**

In `scc/agent.py`, replace:

```python
                tool = find_tool(tool_name)
```

With:

```python
                tool = self._find_tool(tool_name)
```

- [ ] **Step 3: Add _find_tool method to QueryEngine**

In `scc/agent.py`, add this method after `_execute_tool` (before `clear`):

```python
    def _find_tool(self, name: str):
        """
        按名称查找工具（内置 + MCP）。
        对应 Claude Code: findToolByName(assembledTools, name)
        """
        return TOOL_REGISTRY.get(name) or self._extra_registry.get(name)
```

- [ ] **Step 4: Verify agent still works without extra_tools**

```bash
cd F:/code/easycode && python -c "
from scc.agent import QueryEngine
e = QueryEngine()
print('tool count:', len(e._tool_schemas))
print('extra registry:', e._extra_registry)
"
```

Expected:
```
tool count: 6
extra registry: {}
```

- [ ] **Step 5: Commit**

```bash
git add scc/agent.py
git commit -m "feat: QueryEngine accepts extra_tools for MCP integration"
```

---

## Task 7: Modify scc/cli.py — wire MCP into startup + cleanup

**Files:**
- Modify: `scc/cli.py:204-216` (`main()`)

- [ ] **Step 1: Update main() in scc/cli.py**

Replace:

```python
def main() -> None:
    cwd    = os.getcwd()
    client = OllamaClient()

    print_banner(cwd)

    if not check_connection(client):
        sys.exit(1)

    print(HELP)

    engine = QueryEngine(client=client, cwd=cwd)
    repl(engine)
```

With:

```python
def main() -> None:
    cwd    = os.getcwd()
    client = OllamaClient()

    print_banner(cwd)

    if not check_connection(client):
        sys.exit(1)

    # ── MCP 服务器加载 ─────────────────────────────────────
    # 对应 Claude Code: assembleToolPool() MCP 部分
    from .mcp import load_mcp_servers
    p(f"\nLoading MCP servers from {cwd}/mcp.json ...", CYAN)
    mcp_tools, mcp_clients = load_mcp_servers(cwd)
    if mcp_tools:
        p(f"MCP tools loaded: {', '.join(t.name for t in mcp_tools)}", GREEN)
    else:
        p("No MCP servers configured (create mcp.json to add some).", GRAY)

    print(HELP)

    engine = QueryEngine(client=client, cwd=cwd, extra_tools=mcp_tools)
    try:
        repl(engine)
    finally:
        for mc in mcp_clients:
            mc.close()
```

- [ ] **Step 2: Run python main.py and verify startup**

```bash
cd F:/code/easycode && python main.py
```

Expected output includes:
```
Loading MCP servers from .../mcp.json ...
No MCP servers configured (create mcp.json to add some).
```

Then type `/tools` — should show the same 6 built-in tools as before.
Type `/exit` to quit.

- [ ] **Step 3: Smoke test with real mcp.json**

Create `mcp.json` in the project root:

```json
{
  "mcpServers": {
    "fake": {
      "command": "python",
      "args": ["fake_mcp_server.py"]
    }
  }
}
```

Run:

```bash
cd F:/code/easycode && python main.py
```

Expected output includes:
```
Loading MCP servers from .../mcp.json ...
  MCP 'fake': 1 tool(s) loaded
MCP tools loaded: mcp__fake__echo
```

Type `/tools` — should show 7 tools (6 built-in + `mcp__fake__echo`).
Type `/exit`.

- [ ] **Step 4: Remove the test mcp.json**

```bash
cd F:/code/easycode && rm mcp.json
```

- [ ] **Step 5: Run the full test suite**

```bash
cd F:/code/easycode && python test_mcp.py
```

Expected: all 8 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scc/cli.py
git commit -m "feat: wire MCP server loading into CLI startup with graceful cleanup"
```

---

## Self-Review

### Spec coverage

| Spec requirement | Covered by |
|-----------------|-----------|
| stdio MCP only | Task 2 — MCPClient uses subprocess |
| project-level mcp.json | Task 4 — load_mcp_servers reads `<cwd>/mcp.json` |
| broken servers skipped | Task 4 — try/except around connect() |
| tools appear alongside built-ins | Tasks 5+6 — extra param in get_api_schemas, TOOL_REGISTRY + _extra_registry |
| MCPTool name format mcp__s__t | Task 3 |
| initialize handshake | Task 2 — connect() |
| text content concatenation | Task 2 — call_tool() joins type=text blocks |
| timeout values (5s/5s/30s) | Task 2 — connect/list_tools/call_tool defaults |
| close clients on exit | Task 7 — try/finally in main() |
| mcp.json missing → silent | Task 4 — os.path.exists check |

### Placeholder scan

No TBDs, TODOs, or "similar to task N" patterns found.

### Type consistency

- `MCPClient.call_tool()` returns `tuple[str, bool]` — used correctly in `MCPTool.call()`
- `load_mcp_servers()` returns `tuple[list[MCPTool], list[MCPClient]]` — destructured correctly in `main()`
- `QueryEngine(extra_tools=mcp_tools)` — `mcp_tools` is `list[MCPTool]`, accepted as `Optional[list]`
- `get_api_schemas(extra=extra_tools or [])` — `extra` param added in Task 5 matches usage in Task 6
