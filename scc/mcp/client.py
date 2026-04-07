"""
scc/mcp/client.py — MCP stdio transport client
===============================================
对应 Claude Code 源码:
  src/services/mcp/client.ts → MCPClient (stdio transport)

通信协议: JSON-RPC 2.0，每条消息一行 JSON（以 \n 结尾），
通过子进程的 stdin/stdout 传输。
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
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
                stderr=None,
                env=merged_env,
            )
        except FileNotFoundError as e:
            raise MCPError(f"Cannot start server '{self.server_name}': {e}") from e

        # Wrap post-spawn logic to ensure subprocess cleanup on error
        try:
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
        except Exception:
            self.close()
            raise

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
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )
        is_error = bool(result.get("isError", False))
        return text, is_error

    # ── 关闭 ──────────────────────────────────────────────────────────────────

    def close(self) -> None:
        """
        终止子进程。

        Must not be called concurrently with an in-progress _recv.
        Intended use pattern: connect → use → close (single-threaded).
        """
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

        Assumption: Must not be called concurrently with close().
        Single-threaded usage model: connect → requests via _recv → close.
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
                    # Skip notifications (they have no "id" or id is null)
                    if obj.get("id") is None:
                        continue
                    result[0] = obj
                    return
            except MCPError as exc:
                error[0] = exc
            except Exception as exc:
                wrapped = MCPError(f"Protocol error reading from '{self.server_name}': {exc}")
                wrapped.__cause__ = exc
                error[0] = wrapped

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            # Unblock the reader so the daemon thread can terminate cleanly
            try:
                if self._proc and self._proc.stdin:
                    self._proc.stdin.close()
            except Exception:
                pass
            t.join(timeout=1.0)
            raise MCPError(f"Timeout ({timeout}s) waiting for response from '{self.server_name}'")
        if error[0] is not None:
            raise error[0]  # type: ignore[misc]
        return result[0]  # type: ignore[return-value]
