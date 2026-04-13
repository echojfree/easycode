"""
cli.py — 命令行界面
====================
对应 Claude Code 源码:
  src/cli/          — CLI 处理层
  src/main.tsx      — React/Ink TUI 主界面
  src/replLauncher.tsx — REPL 启动器

Claude Code 使用 React + Ink 构建终端 UI，
本实现用 Python print + input 实现等效的 REPL 交互。

主要功能:
  - 连接检查（ping Ollama）
  - REPL 循环（read input → agent → print output）
  - 内置命令（/clear /tools /help /exit）
  - 彩色输出（ANSI 转义码）
"""

from __future__ import annotations
import os
import sys
import threading
from typing import Optional

from .api import OllamaClient, MODEL, OLLAMA_HOST, OLLAMA_PORT
from .agent import QueryEngine
from .mcp import load_mcp_servers
from .tools import get_tools

# ─────────────────────────────────────────────────────────
#  ANSI 颜色
# ─────────────────────────────────────────────────────────
R      = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"


def c(text: str, color: str = R, bold: bool = False) -> str:
    return f"{BOLD if bold else ''}{color}{text}{R}"


def p(text: str, color: str = R, bold: bool = False) -> None:
    print(c(text, color, bold))


# ─────────────────────────────────────────────────────────
#  Spinner — 对应 Claude Code: <Spinner> Ink 组件
#  在 LLM 推理期间显示旋转动画，第一个 token 到来时隐藏
# ─────────────────────────────────────────────────────────
class Spinner:
    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    def __init__(self) -> None:
        self._stop  = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, msg: str = "Thinking") -> None:
        self._stop.clear()
        self._msg = msg
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止动画并清除当前行（幂等：已停止时不写入任何内容）。"""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=0.3)
            self._thread = None
            # 只在 spinner 确实在运行时才清除行，避免二次调用擦除已输出的内容
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

    def _run(self) -> None:
        i = 0
        while not self._stop.wait(0.08):
            frame = self.FRAMES[i % len(self.FRAMES)]
            sys.stdout.write(
                f"\r  {BOLD}{CYAN}{frame} {self._msg}...{R}"
            )
            sys.stdout.flush()
            i += 1


# ─────────────────────────────────────────────────────────
#  欢迎横幅
# ─────────────────────────────────────────────────────────
def print_banner(cwd: str) -> None:
    cwd_short = cwd if len(cwd) <= 36 else "..." + cwd[-33:]
    print(c(f"""
+--------------------------------------------------+
|        Simple Claude Code  (学习版)               |
|                                                  |
|  Model  : {MODEL:<38}|
|  Ollama : {OLLAMA_HOST}:{OLLAMA_PORT:<27}|
|  CWD    : {cwd_short:<38}|
+--------------------------------------------------+
""", CYAN, bold=True))


# ─────────────────────────────────────────────────────────
#  帮助文本
# ─────────────────────────────────────────────────────────
HELP = f"""
{c('Agent 工作流（对应 Claude Code queryLoop）:', YELLOW, True)}
  1. 用户输入  ->  构造消息（含工具定义）->  发给 LLM
  2. LLM 返回 tool_calls  ->  本地执行工具
  3. 工具结果发回 LLM  ->  继续推理
  4. 直到 LLM 无工具调用  ->  输出最终回答

{c('内置命令:', YELLOW, True)}
  /help     显示此帮助
  /tools    列出所有工具及其 JSON Schema
  /clear    清除对话历史（开始新会话）
  /cwd      显示当前工作目录
  /exit     退出
"""


def print_tools(extra: list | None = None) -> None:
    p("\n可用工具:", CYAN, bold=True)
    for tool in get_tools(extra=extra):
        p(f"\n  {tool.name}", GREEN, bold=True)
        p(f"    {tool.description}", R)
        required = tool.input_schema.get("required", [])
        props = tool.input_schema.get("properties", {})
        for pname, pinfo in props.items():
            marker = " *" if pname in required else "  "
            p(f"   {marker}{pname}: {pinfo.get('description', '')}", GRAY)
    print()


# ─────────────────────────────────────────────────────────
#  工具调用 UI 回调
#  对应 Claude Code: renderToolUseMessage / getActivityDescription
# ─────────────────────────────────────────────────────────
def _on_tool_call(tool, tool_name: str, input: dict) -> None:
    if tool:
        display = tool.render_use(input)
    else:
        display = f"{tool_name}({input})"
    p(f"\n  ⟳ {display}", CYAN)


def _on_tool_result(tool, result) -> None:
    preview = result.content
    if len(preview) > 400:
        preview = preview[:400] + "\n  ..."
    color = RED if result.is_error else GRAY
    indented = "\n".join("  " + line for line in preview.splitlines())
    p(indented, color)


# ─────────────────────────────────────────────────────────
#  连接检查
# ─────────────────────────────────────────────────────────
def check_connection(client: OllamaClient) -> bool:
    ok, models = client.ping()
    if not ok:
        p(f"Cannot connect to Ollama at {client.base_url}", RED)
        p("Please ensure Ollama is running.", YELLOW)
        return False

    p(f"Ollama connected ({client.base_url})", GREEN)

    model_found = any(client.model in m for m in models)
    if model_found:
        p(f"Model ready: {client.model}", GREEN)
    else:
        p(f"Model not found: {client.model}", YELLOW)
        if models:
            p(f"Available: {', '.join(models[:5])}", GRAY)
        p(f"Run: ollama pull {client.model}", YELLOW)

    return True


# ─────────────────────────────────────────────────────────
#  REPL 主循环
#  对应 Claude Code: replLauncher + main REPL loop
# ─────────────────────────────────────────────────────────
def repl(engine: QueryEngine) -> None:
    spinner = Spinner()

    while True:
        try:
            user_input = input(c("\nyou> ", BLUE, bold=True)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            p("Bye!", CYAN)
            break

        if not user_input:
            continue

        # ── 内置命令处理 ──────────────────────────────────
        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()

            if cmd in ("/exit", "/quit"):
                p("Bye!", CYAN)
                break

            elif cmd == "/clear":
                engine.clear()
                p("History cleared.", YELLOW)

            elif cmd == "/tools":
                print_tools(extra=list(engine._extra_registry.values()))

            elif cmd in ("/help", "/?"):
                print(HELP)

            elif cmd == "/cwd":
                p(f"CWD: {engine.cwd}", CYAN)

            else:
                p(f"Unknown command: {cmd}  (type /help)", YELLOW)
            continue

        # ── Agent 处理（流式）────────────────────────────
        print()

        # 流式回调状态（用 dict 使闭包可变）
        state = {"first_token": True, "had_tokens": False}

        def on_llm_start() -> None:
            spinner.start()

        def on_llm_end(had_tokens: bool) -> None:
            # 如果没有文本 token（纯工具调用），只需清除 spinner
            # 如果有 token，收尾换行已在 on_token 最后一次调用后由模型内容决定，
            # 但保险起见补一个换行以防模型内容末尾无 \n
            spinner.stop()
            if had_tokens:
                print()  # 确保下一行从行首开始

        def on_token(token: str) -> None:
            # 每次有 token 到来时都尝试停止 spinner（幂等，已停止则无副作用）
            # 这样多轮工具调用时第二轮的 spinner 也能被正确清除
            spinner.stop()
            if state["first_token"]:
                # 第一个 token：打印 "assistant>" 前缀
                sys.stdout.write(c("\nassistant> ", GREEN, bold=True) + "\n")
                state["first_token"] = False
            state["had_tokens"] = True
            sys.stdout.write(c(token, GREEN))
            sys.stdout.flush()

        def on_compact(before: int, after: int) -> None:
            p(f"\n  ⟳ 会话压缩: {before} 条 → {after} 条 (上下文过长，已归档早期历史)", YELLOW)

        try:
            engine.submit_message(
                user_input,
                on_token=on_token,
                on_llm_start=on_llm_start,
                on_llm_end=on_llm_end,
                on_tool_call=_on_tool_call,
                on_tool_result=_on_tool_result,
                on_compact=on_compact,
            )
        except KeyboardInterrupt:
            spinner.stop()
            p("\n[interrupted]", YELLOW)


# ─────────────────────────────────────────────────────────
#  程序入口
# ─────────────────────────────────────────────────────────
def main() -> None:
    cwd    = os.getcwd()
    client = OllamaClient()

    print_banner(cwd)

    if not check_connection(client):
        sys.exit(1)

    # ── MCP 服务器加载 ─────────────────────────────────────
    # 对应 Claude Code: assembleToolPool() MCP 部分
    p(f"\nLoading MCP servers from {cwd}/mcp.json ...", CYAN)
    mcp_tools, mcp_clients = load_mcp_servers(cwd)
    if mcp_tools:
        p(f"MCP tools loaded: {', '.join(t.name for t in mcp_tools)}", GREEN)
    else:
        p("No MCP servers configured (create mcp.json to add some).", GRAY)

    print(HELP)

    engine = QueryEngine(client=client, cwd=cwd, extra_tools=mcp_tools)
    try:
        repl(engine)
    finally:
        for mc in mcp_clients:
            mc.close()
