"""
file_edit_tool.py — 文件精准编辑工具
======================================
对应 Claude Code 源码:
  src/tools/FileEditTool/FileEditTool.ts

Claude Code 的 FileEditTool 设计哲学:
  - 精准替换（old_string → new_string），而非整文件重写
  - old_string 在文件中必须唯一（避免歧义），否则报错
  - 支持多行替换
  - 写入前要求先用 FileReadTool 读取文件（RULES.md 约束）

这种"精准替换"设计让 LLM 不必重写整个文件，
节省 token，也减少因全文重写引入的错误。
"""

import os
import tempfile
from ..tool import Tool
from ..types import ToolContext, ToolResult


class FileEditTool(Tool):
    """
    精准替换文件中的一段文本（第一次出现）。
    对应 Claude Code: FileEditTool (src/tools/FileEditTool/FileEditTool.ts)
    """

    name = "edit_file"
    description = (
        "Edit a file by replacing a specific string with new content. "
        "old_string must appear exactly once in the file to avoid ambiguity. "
        "Always read the file first to ensure old_string is accurate."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": (
                    "The exact text to replace. Must appear exactly once in the file. "
                    "Include enough surrounding context to make it unique."
                ),
            },
            "new_string": {
                "type": "string",
                "description": "The replacement text",
            },
        },
        "required": ["file_path", "old_string", "new_string"],
    }
    is_read_only = False

    def _resolve(self, path: str, cwd: str) -> str:
        return path if os.path.isabs(path) else os.path.join(cwd, path)

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        file_path  = input["file_path"]
        old_string = input["old_string"]
        new_string = input["new_string"]
        abs_path   = self._resolve(file_path, context.cwd)

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return ToolResult(
                content=f"File not found: {file_path}", is_error=True
            )
        except Exception as e:
            return ToolResult(content=f"Read failed: {e}", is_error=True)

        # 唯一性检查（对应 Claude Code: 要求 old_string 唯一）
        count = content.count(old_string)
        if count == 0:
            # 给出上下文帮助 LLM 修正
            preview = repr(old_string[:100]) + ("..." if len(old_string) > 100 else "")
            return ToolResult(
                content=f"String not found in {file_path}: {preview}",
                is_error=True,
            )
        if count > 1:
            return ToolResult(
                content=(
                    f"String appears {count} times in {file_path}. "
                    "Add more surrounding context to make it unique."
                ),
                is_error=True,
            )

        new_content = content.replace(old_string, new_string, 1)

        try:
            # 原子写入（同 FileWriteTool）
            dir_ = os.path.dirname(abs_path) or context.cwd
            fd, tmp = tempfile.mkstemp(dir=dir_)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(new_content)
                os.replace(tmp, abs_path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            return ToolResult(content=f"Write failed: {e}", is_error=True)

        # 统计变化行数
        old_lines = old_string.count("\n") + 1
        new_lines = new_string.count("\n") + 1
        return ToolResult(
            content=f"Edited: {file_path} ({old_lines} lines → {new_lines} lines)"
        )
