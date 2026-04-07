"""
scc — Simple Claude Code
========================
简化版 Claude Code，用于学习 Agent 工作原理。

模块结构（对应 Claude Code 源码）:
  types.py   ←→ src/types/message.ts + Tool.ts (ToolContext)
  tool.py    ←→ src/Tool.ts (Tool/buildTool)
  tools/     ←→ src/tools/* + src/tools.ts
  api.py     ←→ src/services/api/claude.ts
  agent.py   ←→ src/QueryEngine.ts + src/query.ts
  cli.py     ←→ src/cli/ + src/main.tsx
"""

__version__ = "0.1.0"
