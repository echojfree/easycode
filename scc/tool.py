"""
tool.py — 工具基类
==================
对应 Claude Code 源码:
  src/Tool.ts → Tool 类型、buildTool()、ToolDef

Claude Code 用 TypeScript 接口 + buildTool() 工厂函数定义工具:

  export type Tool = {
    name: string
    description: string
    schema: ToolInputJSONSchema
    isEnabled(): boolean
    call(input, context): Promise<Output>
    mapToolResultToToolResultBlockParam(data, toolUseID): ToolResultBlockParam
    renderToolUseMessage(input): ReactNode   // UI 展示
    ...
  }

这里用 Python ABC 抽象基类实现同等概念，保留核心接口。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from .types import ToolContext, ToolResult


class Tool(ABC):
    """
    工具抽象基类。
    每个具体工具继承此类并实现 call()。

    对应 Claude Code 的 buildTool(ToolDef) 返回的对象。
    """

    # ── 子类必须定义的属性 ─────────────────────────────────
    name: str               # 工具标识名（对应 tool_calls[].function.name）
    description: str        # 向 LLM 描述工具用途
    input_schema: dict      # JSON Schema，告诉 LLM 参数格式

    # ── 可选属性 ───────────────────────────────────────────
    is_read_only: bool = False   # 只读工具（参考 FileReadTool.isReadOnly）

    @abstractmethod
    def call(self, input: dict, context: ToolContext) -> ToolResult:
        """
        执行工具逻辑。
        对应 Claude Code: Tool.call(input, toolUseContext)

        input   — 模型传来的参数（已解析为 dict）
        context — 执行环境（cwd、消息历史等）
        返回    — ToolResult（content 会被追加到消息历史）
        """
        ...

    def validate_input(self, input: dict) -> tuple[bool, str]:
        """
        输入验证（可选重写）。
        对应 Claude Code: Tool.validateInput()
        返回 (ok, error_message)
        """
        return True, ""

    def to_api_schema(self) -> dict:
        """
        将工具转换为 Ollama/OpenAI API 格式。
        对应 Claude Code: toolToAPISchema()

        发给 LLM 的工具描述格式:
        {
          "type": "function",
          "function": {
            "name": "...",
            "description": "...",
            "parameters": { JSON Schema }
          }
        }
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def render_use(self, input: dict) -> str:
        """
        UI 展示：工具调用时显示什么。
        对应 Claude Code: Tool.renderToolUseMessage() / getActivityDescription()
        """
        args = ", ".join(f"{k}={repr(v)[:50]}" for k, v in input.items())
        return f"{self.name}({args})"

    def __repr__(self) -> str:
        return f"<Tool:{self.name}>"
