"""
file_write_tool.py — 文件写入工具
==================================
对应 Claude Code 源码:
  src/tools/FileWriteTool/FileWriteTool.ts

Claude Code 的 FileWriteTool 特性（本实现保留核心部分）:
  - 原子写入（写临时文件 → rename，避免写到一半崩溃）
  - 自动创建父目录
  - 权限检查（简化版跳过）
  - 写入后更新 readFileState 缓存（简化版跳过）
"""

import os
import tempfile
from ..tool import Tool
from ..types import ToolContext, ToolResult


class FileWriteTool(Tool):
    """
    创建或完整覆写文件。
    对应 Claude Code: FileWriteTool (src/tools/FileWriteTool/FileWriteTool.ts)
    """

    name = "write_file"
    description = (
        "Create a new file or completely overwrite an existing file. "
        "For modifying specific parts of a file, use edit_file instead."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "The complete content to write to the file",
            },
        },
        "required": ["file_path", "content"],
    }
    is_read_only = False

    def _resolve(self, path: str, cwd: str) -> str:
        return path if os.path.isabs(path) else os.path.join(cwd, path)

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        file_path = input["file_path"]
        content   = input["content"]
        abs_path  = self._resolve(file_path, context.cwd)

        try:
            # 自动创建父目录（对应 Claude Code: mkdirp in FileWriteTool）
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            # 原子写入：先写临时文件，再 rename
            # 对应 Claude Code: writeFile with atomic pattern
            dir_ = os.path.dirname(abs_path) or context.cwd
            fd, tmp = tempfile.mkstemp(dir=dir_)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp, abs_path)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise

            size = len(content.encode("utf-8"))
            return ToolResult(
                content=f"Written: {file_path} ({size} bytes, {content.count(chr(10))+1} lines)"
            )

        except PermissionError:
            return ToolResult(
                content=f"Permission denied: {file_path}", is_error=True
            )
        except Exception as e:
            return ToolResult(content=f"Write failed: {e}", is_error=True)
