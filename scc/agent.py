"""
agent.py — Agent 循环核心
==========================
对应 Claude Code 源码:
  src/QueryEngine.ts  → QueryEngine 类
  src/query.ts        → query() / queryLoop() 函数

Claude Code 的 Agent 循环架构:

  QueryEngine.submitMessage(prompt)
       ↓
  query(params) → AsyncGenerator<StreamEvent | Message>
       ↓
  queryLoop()  [while(true)]
    ├─ 构造系统提示 + 用户上下文
    ├─ callModel(messages, tools)  ← API 调用
    ├─ 解析 tool_use blocks
    │   └─ runTools(toolUseBlocks, toolUseContext)
    │       └─ 每个工具 call() → ToolResult
    ├─ 追加 tool_result 到 messages
    └─ 继续循环，直到无工具调用

  Terminal state → 返回最终文本

关键设计:
  1. State 对象在迭代间流转（messages, turnCount 等）
  2. 工具调用通过 ToolUseContext 访问环境
  3. needsFollowUp 控制是否继续循环
  4. 最大迭代次数防止死循环
"""

from __future__ import annotations
import json
import os
from typing import Optional

from .api import OllamaClient, APIError
from .tool import Tool
from .tools import get_api_schemas, TOOL_REGISTRY
from .types import (
    ToolContext,
    make_system_msg,
    make_user_msg,
    make_assistant_msg,
    make_tool_result_msg,
)

# 对应 Claude Code: MAX_TOOL_ITERATIONS（防死循环上限）
MAX_ITERATIONS = 15

# ─────────────────────────────────────────────────────────
#  系统提示
#  对应 Claude Code: src/bootstrap/state.ts → getSystemPrompt()
#  以及各工具的 prompt() 方法贡献的指令
# ─────────────────────────────────────────────────────────
def build_system_prompt(cwd: str) -> str:
    return f"""You are a professional AI coding assistant (similar to Claude Code).
Current working directory: {cwd}

Available tools: bash, read_file, write_file, edit_file, glob, grep

Rules:
- Always read a file before editing it to ensure accuracy
- Use dedicated tools (read_file, glob, grep) instead of bash equivalents (cat, find, grep)
- Prefer targeted edits (edit_file) over full rewrites (write_file) for existing files
- Be concise and focus on the user's actual need
"""


class QueryEngine:
    """
    Agent 会话管理器。
    对应 Claude Code: QueryEngine (src/QueryEngine.ts)

    职责:
      - 维护消息历史（mutableMessages）
      - 驱动 Agent 循环（submit_message → query loop）
      - 管理工具执行上下文（ToolContext）
    """

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        cwd: Optional[str] = None,
        extra_tools: Optional[list] = None,
    ):
        self.client = client or OllamaClient()
        self.cwd    = cwd or os.getcwd()

        # 对应 Claude Code: QueryEngine.mutableMessages
        # 存储完整对话历史（不含 system prompt）
        self.messages: list[dict] = []

        # MCP 工具注册表（name → Tool），与内置工具分开存储
        self._extra_registry: dict[str, object] = {
            t.name: t for t in (extra_tools or [])
        }

        # 工具 API Schema（缓存，包含 MCP 工具）
        self._tool_schemas = get_api_schemas(extra=extra_tools or [])

        # 当前的 ToolContext（每次 submit_message 时更新 messages）
        self._context = ToolContext(cwd=self.cwd, messages=self.messages)

    # ── 主入口：处理一条用户消息 ────────────────────────────
    def submit_message(
        self,
        user_input: str,
        on_token: Optional[callable] = None,
        on_llm_start: Optional[callable] = None,
        on_llm_end: Optional[callable] = None,
        on_tool_call: Optional[callable] = None,
        on_tool_result: Optional[callable] = None,
    ) -> str:
        """
        处理用户输入，执行完整 Agent 循环，返回最终文本回复。
        对应 Claude Code: QueryEngine.submitMessage() + query() + queryLoop()

        on_token(str)               — 流式文本 token（对应 StreamEvent text_delta）
        on_llm_start()              — LLM 调用开始（显示 spinner）
        on_llm_end(had_tokens:bool) — LLM 流结束（隐藏 spinner）
        on_tool_call(tool, name, input) — 工具调用前（UI 展示）
        on_tool_result(tool, result)    — 工具执行后（UI 展示）
        """
        self.messages.append(make_user_msg(user_input))
        self._context.messages = self.messages
        return self._query_loop(on_token, on_llm_start, on_llm_end,
                                on_tool_call, on_tool_result)

    # ── 核心 Agent 循环 ──────────────────────────────────────
    def _query_loop(
        self,
        on_token: Optional[callable],
        on_llm_start: Optional[callable],
        on_llm_end: Optional[callable],
        on_tool_call: Optional[callable],
        on_tool_result: Optional[callable],
    ) -> str:
        """
        对应 Claude Code: queryLoop() [while(true)]

        流式版循环流程:
          1. on_llm_start()  → 显示 spinner
          2. chat_stream()   → 逐 token yield，最后 yield 完整 message
          3. on_token(tok)   → 实时打印文本
          4. on_llm_end()    → 隐藏 spinner，打印换行
          5. 有 tool_calls   → 执行工具，继续循环
          6. 无 tool_calls   → 返回（Terminal state）
        """
        for iteration in range(1, MAX_ITERATIONS + 1):

            # ── 构造发给 LLM 的消息列表 ─────────────────────────
            full_messages = [
                make_system_msg(build_system_prompt(self.cwd))
            ] + self.messages

            # ── 流式调用 LLM ──────────────────────────────────
            if on_llm_start:
                on_llm_start()

            try:
                had_tokens = False
                final_message: dict = {"role": "assistant", "content": "", "tool_calls": []}

                for item in self.client.chat_stream(
                    messages=full_messages,
                    tools=self._tool_schemas,
                ):
                    if isinstance(item, str):
                        # 文本 token
                        had_tokens = True
                        if on_token:
                            on_token(item)
                    else:
                        # 最终 message dict
                        final_message = item

            except APIError as e:
                if on_llm_end:
                    on_llm_end(had_tokens=False)
                error_msg = f"API error: {e}"
                self.messages.append(make_assistant_msg(error_msg))
                return error_msg

            if on_llm_end:
                on_llm_end(had_tokens=had_tokens)

            content    = final_message.get("content") or ""
            tool_calls = final_message.get("tool_calls") or []

            # ── Terminal state：无工具调用 → 返回最终回复 ──────
            if not tool_calls:
                self.messages.append(make_assistant_msg(content))
                return content

            # ── 有工具调用 → 执行工具 ─────────────────────────
            self.messages.append(
                make_assistant_msg(content, tool_calls=tool_calls)
            )

            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name", "")
                raw_args  = tc.get("function", {}).get("arguments", {})
                call_id   = tc.get("id", f"call_{iteration}")

                if isinstance(raw_args, str):
                    try:
                        tool_input = json.loads(raw_args)
                    except json.JSONDecodeError:
                        tool_input = {}
                else:
                    tool_input = raw_args

                tool = self._find_tool(tool_name)

                if on_tool_call:
                    on_tool_call(tool, tool_name, tool_input)

                result = self._execute_tool(tool, tool_input)

                if on_tool_result:
                    on_tool_result(tool, result)

                self.messages.append(
                    make_tool_result_msg(call_id, result.content)
                )

        # 超过最大迭代次数
        msg = f"Reached maximum iterations ({MAX_ITERATIONS}). Task may be incomplete."
        self.messages.append(make_assistant_msg(msg))
        return msg

    # ── 工具执行（含输入验证 + 错误捕获）───────────────────
    def _execute_tool(self, tool: Optional[Tool], input: dict):
        """
        对应 Claude Code: runTools() 中单个工具的执行路径
        包含: validateInput → call → 错误处理
        """
        from .types import ToolResult

        if tool is None:
            name = input.get("name", "unknown")
            return ToolResult(content=f"Unknown tool: {name}", is_error=True)

        # 输入验证（对应 Claude Code: tool.validateInput()）
        ok, err = tool.validate_input(input)
        if not ok:
            return ToolResult(content=f"Invalid input: {err}", is_error=True)

        try:
            return tool.call(input, self._context)
        except Exception as e:
            return ToolResult(
                content=f"Tool '{tool.name}' raised exception: {e}",
                is_error=True,
            )

    def _find_tool(self, name: str):
        """
        按名称查找工具（内置 + MCP）。
        对应 Claude Code: findToolByName(assembledTools, name)
        """
        return TOOL_REGISTRY.get(name) or self._extra_registry.get(name)

    # ── 会话管理 ─────────────────────────────────────────────
    def clear(self) -> None:
        """
        清除对话历史，开始新会话。
        对应 Claude Code: /clear 命令
        """
        self.messages.clear()
        self._context.messages = self.messages

    @property
    def turn_count(self) -> int:
        """当前对话轮次"""
        return sum(1 for m in self.messages if m.get("role") == "user")
