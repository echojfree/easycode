"""
tools/__init__.py — 工具注册表
==============================
对应 Claude Code 源码:
  src/tools.ts → getAllBaseTools(), getTools(), assembleToolPool()

Claude Code 中工具注册表负责:
  1. 汇总所有工具（核心工具 + MCP 工具 + 功能门控工具）
  2. 按权限模式过滤（bypassPermissions / plan / default）
  3. 去重（同名工具后者覆盖前者）

这里保留核心逻辑：注册所有工具，提供查找接口。
"""

from __future__ import annotations

from .bash_tool      import BashTool
from .file_read_tool import FileReadTool
from .file_write_tool import FileWriteTool
from .file_edit_tool import FileEditTool
from .glob_tool      import GlobTool
from .grep_tool      import GrepTool

from ..tool import Tool


# ─────────────────────────────────────────────────────────
#  工具注册表
#  对应 Claude Code: getAllBaseTools() 返回的工具列表
#
#  Claude Code 用 toolMatchesName() + Map 管理工具，
#  这里简化为 dict[name -> Tool 实例]。
# ─────────────────────────────────────────────────────────
_ALL_TOOLS: list[Tool] = [
    BashTool(),
    FileReadTool(),
    FileWriteTool(),
    FileEditTool(),
    GlobTool(),
    GrepTool(),
]

# name → Tool，用于快速查找
TOOL_REGISTRY: dict[str, Tool] = {t.name: t for t in _ALL_TOOLS}


def get_tools(extra: list[Tool] | None = None) -> list[Tool]:
    """
    返回所有可用工具列表（含 MCP 工具）。
    对应 Claude Code: assembleToolPool() — 内置工具优先，按名称去重。

    extra: 额外工具列表（如 MCP 工具），追加到内置工具之后。
    内置工具名称发生冲突时优先保留内置工具（与 Claude Code uniqBy 行为一致）。
    """
    seen: set[str] = {t.name for t in _ALL_TOOLS}
    extra_deduped = [t for t in (extra or []) if t.name not in seen]
    return list(_ALL_TOOLS) + extra_deduped


def get_api_schemas(extra: list[Tool] | None = None) -> list[dict]:
    """
    返回工具的 API Schema 列表，用于发送给 LLM。
    对应 Claude Code: tools.map(t => toolToAPISchema(t))

    extra: 额外工具列表（如 MCP 工具）。
    """
    return [t.to_api_schema() for t in get_tools(extra)]


def find_tool(name: str) -> Tool | None:
    """
    按名称查找工具。
    对应 Claude Code: findToolByName(tools, name)
    """
    return TOOL_REGISTRY.get(name)


__all__ = [
    "TOOL_REGISTRY",
    "get_tools",
    "get_api_schemas",
    "find_tool",
    "BashTool",
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "GlobTool",
    "GrepTool",
]
