"""
bash_tool.py — Shell 命令执行工具
==================================
对应 Claude Code 源码:
  src/tools/BashTool/BashTool.tsx
  src/tools/BashTool/prompt.ts  → getSimplePrompt()

Claude Code 的 BashTool 特性（本实现保留核心部分）:
  - 超时控制（默认 120s，最大 10min）
  - 工作目录跟踪（cwd 持久化）
  - stdout / stderr 分离
  - 退出码检查
  - background 运行支持（简化版不实现）
  - sandbox 模式（简化版不实现）
"""

import subprocess
from ..tool import Tool
from ..types import ToolContext, ToolResult

# 对应 Claude Code: getDefaultTimeoutMs() / getMaxTimeoutMs()
DEFAULT_TIMEOUT_S = 120
MAX_TIMEOUT_S     = 600


class BashTool(Tool):
    """
    在工作目录下执行 shell 命令。
    对应 Claude Code: BashTool (src/tools/BashTool/BashTool.tsx)
    """

    name = "bash"
    description = (
        "Execute a shell command in the working directory and return its output. "
        "Use for running scripts, installing packages, git operations, etc. "
        "Prefer dedicated tools (read_file, write_file, glob, grep) over "
        "shell equivalents (cat, echo, find, grep) when available."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "description": {
                "type": "string",
                "description": "Short description of what this command does",
            },
            "timeout": {
                "type": "integer",
                "description": f"Timeout in seconds (default {DEFAULT_TIMEOUT_S}, max {MAX_TIMEOUT_S})",
            },
        },
        "required": ["command"],
    }
    is_read_only = False

    def validate_input(self, input: dict) -> tuple[bool, str]:
        timeout = input.get("timeout", DEFAULT_TIMEOUT_S)
        if timeout > MAX_TIMEOUT_S:
            return False, f"Timeout {timeout}s exceeds maximum {MAX_TIMEOUT_S}s"
        return True, ""

    def call(self, input: dict, context: ToolContext) -> ToolResult:
        command     = input["command"]
        timeout_s   = min(int(input.get("timeout", DEFAULT_TIMEOUT_S)), MAX_TIMEOUT_S)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=context.cwd,
                timeout=timeout_s,
                # 对应 Claude Code: shell state is initialized from user profile
                env=None,
            )

            # 组合输出（对应 Claude Code: BashTool 合并 stdout/stderr）
            parts = []
            if result.stdout.strip():
                parts.append(result.stdout)
            if result.stderr.strip():
                parts.append(f"[stderr]\n{result.stderr}")
            if result.returncode != 0:
                parts.append(f"[exit code: {result.returncode}]")

            content = "\n".join(parts).strip() or "(no output)"
            # 非零退出码视为错误，LLM 可据此判断是否重试
            return ToolResult(content=content, is_error=(result.returncode != 0))

        except subprocess.TimeoutExpired:
            return ToolResult(
                content=f"Command timed out after {timeout_s}s",
                is_error=True,
            )
        except Exception as e:
            return ToolResult(content=f"Execution failed: {e}", is_error=True)

    def render_use(self, input: dict) -> str:
        desc = f"  # {input['description']}" if input.get("description") else ""
        return f"$ {input['command']}{desc}"
