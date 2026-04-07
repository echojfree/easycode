"""
glob_tool.py — 文件模式匹配工具
================================
对应 Claude Code 源码:
  src/tools/GlobTool/GlobTool.ts

Claude Code 的 GlobTool 特性:
  - 支持 ** 递归匹配
  - 按修改时间排序（最近修改的优先）
  - 跳过 .git、node_modules 等目录
  - 返回相对路径（相对于 cwd）
"""

import os
import glob as glob_module
from ..tool import Tool
from ..types import ToolContext, ToolResult

# 对应 Claude Code: SKIP_DIRS in GlobTool
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", ".next"}


class GlobTool(Tool):
    """
    使用 glob 模式查找文件。
    对应 Claude Code: GlobTool (src/tools/GlobTool/GlobTool.ts)
    """

    name = "glob"
    description = (
        "Find files matching a glob pattern. Supports ** for recursive search. "
        "Results are sorted by modification time (most recent first)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '**/*.py', 'src/**/*.ts', '*.json'",
            },
            "path": {
                "type": "string",
                "description": "Base directory to search in (default: cwd)",
            },
        },
        "required": ["pattern"],
    }
    is_read_only = True

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        pattern  = input["pattern"]
        base_dir = input.get("path") or ""

        # 解析基础目录
        if base_dir and not os.path.isabs(base_dir):
            base_dir = os.path.join(context.cwd, base_dir)
        elif not base_dir:
            base_dir = context.cwd

        try:
            full_pattern = os.path.join(base_dir, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)

            # 过滤跳过目录中的文件
            filtered = [
                m for m in matches
                if not any(
                    part in SKIP_DIRS
                    for part in os.path.normpath(m).split(os.sep)
                )
            ]

            if not filtered:
                return ToolResult(content=f"No files found matching '{pattern}'")

            # 按修改时间降序排序（最近修改的优先）
            filtered.sort(key=lambda p: os.path.getmtime(p), reverse=True)

            # 转为相对路径
            rels = []
            for m in filtered:
                try:
                    rels.append(os.path.relpath(m, context.cwd))
                except ValueError:
                    rels.append(m)

            return ToolResult(
                content=f"Found {len(rels)} files:\n" + "\n".join(rels)
            )

        except Exception as e:
            return ToolResult(content=f"Glob failed: {e}", is_error=True)
