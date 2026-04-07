"""
grep_tool.py — 内容搜索工具
============================
对应 Claude Code 源码:
  src/tools/GrepTool/GrepTool.ts

Claude Code 的 GrepTool 特性:
  - 基于 ripgrep (rg)，支持正则和字面量搜索
  - 返回 file:line:content 格式
  - 支持文件类型过滤（--type js 等）
  - 上下文行（-C/-A/-B）
  - 递归搜索，自动跳过 .git / node_modules

简化版用 Python re 模块实现同等功能，无需外部依赖。
"""

import os
import re
from ..tool import Tool
from ..types import ToolContext, ToolResult

MAX_RESULTS  = 100   # 最多返回条数（防止结果过长）
SKIP_DIRS    = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist"}


class GrepTool(Tool):
    """
    在文件或目录中搜索正则表达式内容。
    对应 Claude Code: GrepTool (src/tools/GrepTool/GrepTool.ts)
    """

    name = "grep"
    description = (
        "Search file contents using a regex pattern. "
        "Returns matches in 'file:line:content' format. "
        "Use for finding function definitions, usages, imports, etc."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search (default: cwd)",
            },
            "include": {
                "type": "string",
                "description": "File glob filter, e.g. '*.py', '*.{ts,tsx}'",
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Case-insensitive search (default false)",
            },
        },
        "required": ["pattern"],
    }
    is_read_only = True

    def _matches_include(self, filename: str, include: str | None) -> bool:
        """简单的 glob 文件名过滤"""
        if not include:
            return True
        import fnmatch
        # 支持 {a,b} 格式：拆开多个模式
        if "{" in include and "}" in include:
            inner = include[include.index("{") + 1: include.index("}")]
            prefix = include[: include.index("{")]
            suffix = include[include.index("}") + 1:]
            patterns = [prefix + p + suffix for p in inner.split(",")]
        else:
            patterns = [include]
        return any(fnmatch.fnmatch(filename, p) for p in patterns)

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        pattern          = input["pattern"]
        search_path      = input.get("path") or ""
        include          = input.get("include")
        case_insensitive = bool(input.get("case_insensitive", False))

        # 解析搜索路径
        if search_path and not os.path.isabs(search_path):
            search_path = os.path.join(context.cwd, search_path)
        elif not search_path:
            search_path = context.cwd

        # 编译正则
        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(content=f"Invalid regex: {e}", is_error=True)

        results: list[str] = []
        truncated = False

        def search_file(fp: str) -> None:
            nonlocal truncated
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            rel = os.path.relpath(fp, context.cwd)
                            results.append(f"{rel}:{lineno}: {line.rstrip()}")
                            if len(results) >= MAX_RESULTS:
                                truncated = True
                                return
            except (PermissionError, OSError):
                pass

        try:
            if os.path.isfile(search_path):
                search_file(search_path)
            elif os.path.isdir(search_path):
                for root, dirs, files in os.walk(search_path):
                    # 跳过无关目录（原地修改 dirs 以阻止递归进入）
                    dirs[:] = [
                        d for d in dirs
                        if d not in SKIP_DIRS and not d.startswith(".")
                    ]
                    for fn in files:
                        if truncated:
                            break
                        if self._matches_include(fn, include):
                            search_file(os.path.join(root, fn))
            else:
                return ToolResult(
                    content=f"Path not found: {search_path}", is_error=True
                )
        except Exception as e:
            return ToolResult(content=f"Search failed: {e}", is_error=True)

        if not results:
            return ToolResult(content=f"No matches found for '{pattern}'")

        output = "\n".join(results)
        if truncated:
            output += f"\n... (truncated at {MAX_RESULTS} results)"
        return ToolResult(content=output)
