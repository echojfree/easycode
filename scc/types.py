"""
types.py — 核心数据类型
======================
对应 Claude Code 源码:
  src/types/message.ts   — 消息类型
  src/Tool.ts (部分)     — ToolContext, ToolResult

Claude Code 的消息体系:
  UserMessage      用户输入 + 工具结果
  AssistantMessage 模型回复（可含 tool_calls）
  SystemMessage    系统级消息

这里用更简洁的 Python 数据类 + 工厂函数实现同等概念。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import os


# ─────────────────────────────────────────────────────────
#  ToolContext
#  对应 Claude Code: src/Tool.ts → ToolUseContext
#
#  Claude Code 的 ToolUseContext 包含几十个字段（权限、MCP、
#  文件缓存、abort controller 等）。这里保留学习所需的核心子集。
# ─────────────────────────────────────────────────────────
@dataclass
class ToolContext:
    """
    工具执行上下文，传递给每个工具的 call() 方法。
    让工具能感知运行环境，而不依赖全局变量。
    """
    cwd: str = field(default_factory=os.getcwd)
    # 当前对话消息历史（工具可以读取，但不应直接修改）
    messages: list[dict] = field(default_factory=list)


# ─────────────────────────────────────────────────────────
#  ToolResult
#  对应 Claude Code: 工具 call() 的返回值
# ─────────────────────────────────────────────────────────
@dataclass
class ToolResult:
    """
    工具执行结果。
    content   — 文本内容，回传给 LLM
    is_error  — 是否为错误（LLM 可据此决策是否重试）
    """
    content: str
    is_error: bool = False

    def __str__(self) -> str:
        return self.content


# ─────────────────────────────────────────────────────────
#  消息工厂函数
#  对应 Claude Code: src/utils/messages.ts 中的 create* 函数
#
#  Ollama /api/chat 消息格式与 OpenAI 兼容:
#    role: "system" | "user" | "assistant" | "tool"
# ─────────────────────────────────────────────────────────

def make_system_msg(content: str) -> dict:
    """createSystemMessage"""
    return {"role": "system", "content": content}


def make_user_msg(content: str) -> dict:
    """createUserMessage — 用户纯文本输入"""
    return {"role": "user", "content": content}


def make_assistant_msg(content: str, tool_calls: Optional[list] = None) -> dict:
    """
    createAssistantMessage — 模型回复。
    tool_calls 不为空时表示模型希望调用工具。
    """
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def make_tool_result_msg(tool_call_id: str, content: str) -> dict:
    """
    工具执行结果消息。
    tool_call_id 与 assistant 消息中的 tool_calls[i].id 对应，
    LLM 凭此知道哪个工具调用对应哪个结果。
    对应 Claude Code: ToolResultBlockParam
    """
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content,
    }
