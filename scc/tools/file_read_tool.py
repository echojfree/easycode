"""
file_read_tool.py — 文件读取工具
=================================
对应 Claude Code 源码:
  src/tools/FileReadTool/FileReadTool.ts

Claude Code 的 FileReadTool 特性（本实现保留核心部分）:
  - offset / limit 分页读取（避免大文件占满上下文）
  - 带行号输出（addLineNumbers）
  - 文件大小 / token 数限制
  - 图片、PDF、Notebook 类型支持（简化版只处理文本）
  - 文件未变更时返回 FILE_UNCHANGED_STUB（去重优化）
"""

import os
from ..tool import Tool
from ..types import ToolContext, ToolResult

# 对应 Claude Code: getDefaultFileReadingLimits()
DEFAULT_LIMIT  = 2000   # 默认最多读取行数
MAX_LINE_WIDTH = 2000   # 单行截断宽度


class FileReadTool(Tool):
    """
    读取文件内容，带行号，支持分页。
    对应 Claude Code: FileReadTool (src/tools/FileReadTool/FileReadTool.ts)
    """

    name = "read_file"
    description = (
        "Read the contents of a file. Shows line numbers. "
        "Use offset and limit to read specific portions of large files."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                # 对应 Claude Code: "The absolute path to the file to read"
                "description": "Path to the file (absolute or relative to cwd)",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based, default 1)",
            },
            "limit": {
                "type": "integer",
                "description": f"Number of lines to read (default {DEFAULT_LIMIT})",
            },
        },
        "required": ["file_path"],
    }
    is_read_only = True

    def _resolve(self, path: str, cwd: str) -> str:
        """路径解析：相对路径 → 绝对路径（基于 cwd）"""
        return path if os.path.isabs(path) else os.path.join(cwd, path)

    def validate_input(self, input: dict) -> tuple[bool, str]:
        offset = input.get("offset", 1)
        limit  = input.get("limit", DEFAULT_LIMIT)
        if isinstance(offset, int) and offset < 1:
            return False, "offset must be >= 1"
        if isinstance(limit, int) and limit < 1:
            return False, "limit must be >= 1"
        return True, ""

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        file_path = input["file_path"]
        offset    = int(input.get("offset", 1))
        limit     = int(input.get("limit", DEFAULT_LIMIT))

        abs_path  = self._resolve(file_path, context.cwd)

        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)

            # offset 转 0-based 索引（对应 Claude Code: const lineOffset = offset - 1）
            start = max(0, offset - 1)
            end   = min(start + limit, total_lines)
            chunk = all_lines[start:end]

            # 带行号格式化（对应 Claude Code: addLineNumbers(file)）
            numbered = "".join(
                f"{start + i + 1:4d}\t{line[:MAX_LINE_WIDTH]}"
                for i, line in enumerate(chunk)
            )

            # 分页提示（帮助 LLM 知道文件还有更多内容）
            header = (
                f"File: {file_path} "
                f"(lines {offset}-{offset + len(chunk) - 1}/{total_lines})\n\n"
                if total_lines > limit
                else f"File: {file_path} ({total_lines} lines)\n\n"
            )

            return ToolResult(content=header + numbered)

        except FileNotFoundError:
            return ToolResult(
                content=f"File not found: {file_path}\n(cwd: {context.cwd})",
                is_error=True,
            )
        except IsADirectoryError:
            return ToolResult(
                content=f"Path is a directory, not a file: {file_path}",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Read failed: {e}", is_error=True)

    def render_use(self, input: dict) -> str:
        parts = [input["file_path"]]
        if "offset" in input:
            parts.append(f"offset={input['offset']}")
        if "limit" in input:
            parts.append(f"limit={input['limit']}")
        return f"read_file({', '.join(parts)})"
