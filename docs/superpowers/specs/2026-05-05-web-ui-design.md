# easycode Web UI 设计文档

**日期**: 2026-05-05  
**状态**: 已批准  
**技术栈**: FastAPI + SSE + React + Vite + Tailwind CSS  
**设计参考**: `DESIGN.md`（Anthropic/Claude 品牌体系）

---

## 目标

将现有 easycode CLI agent（Python + Ollama）改造为 Web 界面，保留 CLI 入口不变，新增 Web 服务层和 React 前端，实现流式 AI 回复。

---

## 文件结构

```
F:/code/easycode/
├── main.py                  # 保留，CLI 入口不变
├── web_server.py            # NEW: FastAPI 服务入口
├── requirements.txt         # 追加 fastapi, uvicorn[standard], sse-starlette
│
├── scc/
│   ├── api.py               # 改：新增 generate_stream() 方法
│   ├── agent.py             # 改：新增 run_stream() 生成器
│   └── ...（其余不动）
│
└── frontend/
    ├── package.json
    ├── vite.config.js        # 开发时 /api 代理到 :8000
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx            # 顶层状态：view, messages, isStreaming
        ├── pages/
        │   ├── HomePage.jsx
        │   └── ChatPage.jsx
        └── components/
            ├── MessageList.jsx
            ├── MessageItem.jsx    # user 气泡 / AI 文本 + markdown
            ├── InputBar.jsx
            └── ToolCallBadge.jsx
```

---

## 后端 API

### 核心接口

```
POST /api/chat/stream
Content-Type: application/json
Body: { "message": "用户输入", "conversation_id": "uuid" }
Response: text/event-stream (SSE)
```

### SSE 事件格式

```
data: {"type": "token",      "content": "文字片段"}
data: {"type": "tool_start", "tool": "bash_tool", "input": "ls -la"}
data: {"type": "tool_end",   "tool": "bash_tool", "output": "结果"}
data: {"type": "done"}
data: {"type": "error",      "message": "错误信息"}
```

### 辅助接口

```
POST /api/clear     清空会话历史，返回 {"ok": true}
GET  /api/health    返回 {"status": "ok", "model": "gpt-oss:20b", "host": "..."}
GET  /              返回 React 构建产物 index.html（生产模式）
```

---

## 后端流式实现

### `scc/api.py` 新增

```python
def generate_stream(self, messages, tools=None):
    """向 Ollama 发送流式请求，逐行 yield token 字符串"""
    payload = {
        "model": self.model,
        "messages": messages,
        "tools": tools or [],
        "stream": True,
    }
    with requests.post(self.url, json=payload, stream=True, timeout=self.timeout) as resp:
        for line in resp.iter_lines():
            if line:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    # 返回 tool_calls（如有）
                    yield chunk
                    break
```

### `scc/agent.py` 新增

```python
def run_stream(self, user_input: str):
    """
    agent 循环的流式版本，yield 事件 dict：
      {"type": "token",      "content": "..."}
      {"type": "tool_start", "tool": "...", "input": "..."}
      {"type": "tool_end",   "tool": "...", "output": "..."}
      {"type": "done"}
      {"type": "error",      "message": "..."}
    """
```

### `web_server.py`

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import json

app = FastAPI()

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    def event_generator():
        for event in engine.run_stream(req.message):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 前端组件设计

### 状态结构（App.jsx）

```js
// 顶层状态
{
  view: "home" | "chat",
  messages: [
    {
      id: "uuid",
      role: "user" | "assistant",
      content: "文字内容",
      toolCalls: [
        { tool: "bash_tool", input: "...", output: "...", status: "running" | "done" }
      ]
    }
  ],
  isStreaming: false,
  currentStreamText: ""   // 正在流入的 token 累积
}
```

### 组件职责

| 组件 | 职责 |
|------|------|
| `HomePage` | 居中布局，Cormorant Garamond serif 大标题，输入框，快捷 pills |
| `ChatPage` | 顶栏 + `MessageList` + `InputBar` |
| `MessageList` | 滚动容器，自动 scrollIntoView |
| `MessageItem` | user=右对齐气泡；assistant=左对齐文本 + spike + react-markdown |
| `ToolCallBadge` | running 时 coral 脉冲点；done 时折叠输出 |
| `InputBar` | enter 发送，shift+enter 换行；流式中禁用；model 显示 |

### SSE 接入（useChatStream hook）

```js
const sendMessage = (text) => {
  // 1. 追加用户消息到 messages
  // 2. 追加空 assistant 消息（id=pending）
  // 3. 开启 EventSource / fetch ReadableStream
  // 4. token → 累积到 currentStreamText → 更新 pending 消息 content
  // 5. tool_start/end → 更新 pending 消息的 toolCalls
  // 6. done → isStreaming=false，清空 currentStreamText
}
```

---

## UI 设计规范（来自 DESIGN.md）

| 元素 | Token | 值 |
|------|-------|----|
| 页面底色 | `canvas` | `#faf9f5` |
| 主色/CTA | `primary` | `#cc785c` |
| 暗色面板 | `surface-dark` | `#181715` |
| 用户气泡 | `surface-card` | `#efe9de` |
| 主文字 | `ink` | `#141413` |
| 次要文字 | `muted` | `#6c6a64` |
| 大标题字体 | display-md | Cormorant Garamond, serif, 400, -0.5px |
| 正文字体 | body-md | Inter, sans-serif, 400, 16px |
| 代码字体 | code | JetBrains Mono, 14px |
| 按钮圆角 | rounded-md | 8px |
| 卡片圆角 | rounded-lg | 12px |
| 标签圆角 | pill | 9999px |

---

## 测试策略

| 层次 | 内容 |
|------|------|
| 后端单元 | `test_web_server.py`：TestClient 测 `/health`、`/clear`；mock QueryEngine 测 SSE 事件格式 |
| 流式集成 | `test_streaming.py`：验证 token 事件流完整性（需 Ollama 在线） |
| 前端手动 | DevTools Network 面板验证 SSE 帧；多轮对话；工具调用可见性 |
| 回归 | `test_full.py`（36个）+ `test_mcp.py`（8个）继续通过，确保 CLI 不受影响 |

---

## 运行方式

```bash
# 后端
pip install fastapi "uvicorn[standard]" sse-starlette
python web_server.py          # 监听 :8000

# 前端（开发）
cd frontend
npm install
npm run dev                   # 监听 :5173，/api 代理到 :8000

# 前端（生产构建）
npm run build                 # 产物输出到 frontend/dist/
# FastAPI 静态文件服务 frontend/dist/
```

---

## 不在本次范围内

- 用户登录/认证
- 会话持久化（刷新后历史消失）
- MCP sse/http transport（仅 stdio）
- 移动端响应式（桌面优先）
- 深色模式切换
