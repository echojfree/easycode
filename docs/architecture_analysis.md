# EasyCode 项目架构与原理分析文档

## 1. 项目概述

`EasyCode` 是一个基于 Python 实现的本地 AI Agent CLI 学习版项目。其核心设计目标是拆解并模拟 `Claude Code` 等先进终端 AI 编程助手的实现原理，研究其 **Agent Loop (智能体循环)**、**Tool Use (工具调用)**、**Context Management (上下文管理)** 以及 **MCP (Model Context Protocol) 接入** 等核心机制。

该项目并非商业成品，而是作为一个教学样例，展示如何构建一个能够感知文件系统、执行命令并根据 LLM 指令自主进行多轮决策的智能体。

---

## 2. 核心架构设计

项目的架构遵循典型的 Agent 设计模式，主要分为以下四个层级：

### 2.1 用户交互层 (CLI Layer)
- **实现模块**: `scc/cli.py`
- **职责**: 
    - 提供 REPL (Read-Eval-Print Loop) 交互环境。
    - 管理终端 UI 展示（使用 ANSI 转义码实现彩色输出和 Spinner 动画）。
    - 处理内置命令（如 `/clear`, `/tools`, `/exit`）。
    - 将用户输入传递给 Agent 引擎。

### 2.2 智能体逻辑层 (Agent Engine Layer)
- **实现模块**: `scc/agent.py`
- **核心机制: Agent Loop (智能体循环)**
  Agent 的生命周期由 `QueryEngine.submit_message` 驱动，其核心逻辑是一个 `while` 循环：
  1. **构造上下文**: 结合系统提示词 (System Prompt) 和历史消息记录。
  2. **模型决策**: 调用 LLM API，获取模型回复。
  3. **解析意图**: 
     - 若模型返回**纯文本** $\rightarrow$ 直接输出给用户，结束当前轮次。
     - 若模型返回 **`tool_calls`** $\rightarrow$ 进入工具执行阶段。
  4. **工具执行**: 遍历模型请求的所有工具，调用对应的 `Tool.call()` 方法。
  5. **反馈循环**: 将工具执行的结果（成功或失败）封装为 `tool_result` 消息，追加到对话历史中，重新回到步骤 1，直到模型不再请求工具或达到最大迭代次数 (`MAX_ITERATIONS`)。

### 2.3 工具执行层 (Tooling Layer)
- **实现模块**: `scc/tool.py`, `scc/tools/`
- **设计模式**: 采用抽象基类 `Tool` 定义统一接口。
- **关键组件**:
    - **`Tool` 基类**: 定义了 `name`, `description`, `input_schema` (JSON Schema) 以及 `call()` 方法。
    - **内置工具集**: 包含 `bash_tool.py` (执行命令), `file_read_tool.py` (读取文件), `file_edit_tool.py` (智能编辑文件) 等。
    - **输入验证**: 每个工具都支持 `validate_input()`，在执行前确保 LLM 提供的参数符合要求。

### 2.4 协议与通信层 (API & Protocol Layer)
- **实现模块**: `scc/api.py`, `scc/mcp/`
- **LLM 通信**: `OllamaClient` 封装了与本地 Ollama 服务的 HTTP 通信，支持流式 (Streaming) 和非流式请求，并实现了与 OpenAI/Claude 兼容的工具调用协议。
- **MCP 协议支持**: 通过 `scc/mcp/` 实现对 Model Context Protocol 的初步支持，允许 Agent 动态加载外部定义的 MCP Server 工具，扩展其能力边界。

---

## 3. 核心原理详解

### 3.1 智能体循环 (The Agent Loop)
这是 Agent 的“大脑”运作方式。不同于传统的“一问一答”模式，Agent Loop 是**目标导向**的。
- **多轮推理**: 模型可以通过多次 `tool_use` $\rightarrow$ `tool_result` $\rightarrow$ `tool_use` 的循环，逐步完成复杂任务（例如：先 `ls` 查看目录 $\rightarrow$ 再 `read_file` 阅读代码 $\rightarrow$ 最后 `edit_file` 修改 Bug）。
- **终止条件**: 只有当模型认为任务已完成，返回一段纯文本描述结果时，循环才会自然终止。

### 3.2 上下文与内存管理 (Context Management)
为了防止对话过长导致超出 LLM 的上下文窗口 (Context Window)，项目实现了：
- **消息历史维护**: `QueryEngine` 持有 `messages` 列表，记录完整的对话轨迹。
- **上下文压缩 (Compaction)**: 当消息量过大时，通过 `_apply_tool_result_budget` 等机制对超长的工具输出结果进行截断或摘要处理，确保模型始终能接收到最关键的信息。

### 3.3 工具调用协议 (Tool Use Protocol)
模型并不直接操作文件，而是通过**声明式指令**实现：
1. 模型通过 `tool_calls` 发送一个结构化的 JSON 报文（包含工具名和参数）。
2. 本地代码解析该 JSON，匹配到对应的 `Tool` 实例。
3. 本地代码在受控的环境中执行真实的系统操作。
4. 执行结果被转译为模型可理解的 `role: tool` 消息反馈回去。

---

## 4. 总结

`EasyCode` 通过高度模块化的设计，清晰地展示了现代 AI Agent 的工作流程：**用户意图 $\rightarrow$ 模型决策 $\rightarrow$ 工具执行 $\rightarrow$ 结果反馈 $\rightarrow$ 模型再决策**。这种“观察-行动-思考”的循环是实现自主编程助手、自动化运维助手等高级应用的核心基石。
