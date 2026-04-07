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

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        text, is_error = self._client.call_tool(
            name=self._tool_name,
            arguments=input,
        )
        return ToolResult(content=text, is_error=is_error)

    def render_use(self, input: dict) -> str:
        return f"[MCP:{self._server_name}] {self._tool_name}({input})"
