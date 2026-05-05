"""
Web server — FastAPI + SSE
===========================
将 easycode CLI agent 以 HTTP API 形式暴露。

运行：
    python web_server.py          # 监听 0.0.0.0:8000
    python web_server.py --port 9000

接口：
    GET  /api/health              健康检查
    POST /api/chat/stream         SSE 流式对话
    POST /api/clear               清空会话历史
    GET  /                        (生产模式) 返回 React 产物
"""
from __future__ import annotations
import json
import os
import pathlib
import queue
import threading
from typing import Generator


def _load_dotenv_override() -> None:
    """Load .env file, overriding any existing env vars.

    Unlike main.py's _load_dotenv() (which skips already-set vars),
    this version forces .env values so the shell environment cannot
    accidentally override Ollama connection settings.
    """
    env_file = pathlib.Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ[key.strip()] = val.strip()


# Must run before any scc.api import so OLLAMA_HOST etc. are correct
_load_dotenv_override()

import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

UPLOAD_DIR = pathlib.Path(__file__).parent / "upload"
UPLOAD_DIR.mkdir(exist_ok=True)

from scc.agent import QueryEngine
from scc.api import OllamaClient, OLLAMA_HOST, OLLAMA_PORT, MODEL as OLLAMA_MODEL
from scc.openai_client import OpenAIClient, OPENAI_BASE_URL, OPENAI_MODEL
from scc.embedding_client import EmbeddingClient
from scc.mcp import load_mcp_servers

# ── Provider 选择 ────────────────────────────────────────────
PROVIDER = os.environ.get("PROVIDER", "ollama").lower()

def _build_client():
    if PROVIDER == "openai":
        return OpenAIClient()
    return OllamaClient()

# ── 全局 engine（单用户本地应用，共享实例） ──────────────────
_mcp_tools, _mcp_clients = load_mcp_servers(".")
_client = _build_client()
_embed_client = EmbeddingClient()
engine = QueryEngine(client=_client, extra_tools=_mcp_tools)
_engine_lock = threading.Lock()   # 防止并发请求同时修改 messages

# ── FastAPI 应用 ─────────────────────────────────────────────
app = FastAPI(title="easycode API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 请求模型 ─────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str


# ── /api/health ──────────────────────────────────────────────
@app.get("/api/health")
def health():
    ok, models = _client.ping()
    if PROVIDER == "openai":
        host = OPENAI_BASE_URL
        model = OPENAI_MODEL
    else:
        host = f"{OLLAMA_HOST}:{OLLAMA_PORT}"
        model = OLLAMA_MODEL
    return {
        "status":           "ok",
        "provider":         PROVIDER,
        "model":            model,
        "host":             host,
        "llm_reachable":    ok,
        "available_models": models,
    }


# ── /api/providers ────────────────────────────────────────────
@app.get("/api/providers")
def list_providers():
    """列出可用的 provider 配置及连通性状态。"""
    result = []

    # Ollama
    ollama = OllamaClient()
    ok_o, models_o = ollama.ping()
    result.append({
        "id":      "ollama",
        "label":   f"Ollama ({OLLAMA_MODEL})",
        "model":   OLLAMA_MODEL,
        "host":    f"{OLLAMA_HOST}:{OLLAMA_PORT}",
        "active":  PROVIDER == "ollama",
        "ok":      ok_o,
        "models":  models_o[:10],          # 只返回前 10 个
    })

    # OpenAI-compatible
    openai_cli = OpenAIClient()
    ok_ai, models_ai = openai_cli.ping()
    result.append({
        "id":      "openai",
        "label":   f"OpenAI-compatible ({OPENAI_MODEL})",
        "model":   OPENAI_MODEL,
        "host":    OPENAI_BASE_URL,
        "active":  PROVIDER == "openai",
        "ok":      ok_ai,
        "models":  models_ai[:10],
    })

    # Embedding
    ok_emb, emb_size = _embed_client.ping()
    result.append({
        "id":      "embedding",
        "label":   f"Embedding ({os.environ.get('EMBEDDING_MODEL', '')})",
        "model":   os.environ.get("EMBEDDING_MODEL", ""),
        "host":    os.environ.get("EMBEDDING_BASE_URL", ""),
        "active":  False,
        "ok":      ok_emb,
        "dim":     emb_size,
    })

    return {"providers": result, "current": PROVIDER}


# ── /api/upload ──────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """接收文件并保存到本地 upload/ 目录。"""
    safe_name = pathlib.Path(file.filename).name  # 去掉路径穿越
    dest = UPLOAD_DIR / safe_name
    # 同名文件加序号
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        counter += 1
    content = await file.read()
    dest.write_bytes(content)
    return {"filename": dest.name, "path": f"upload/{dest.name}", "size": len(content)}


# ── /api/clear ───────────────────────────────────────────────
@app.post("/api/clear")
def clear_history():
    with _engine_lock:
        engine.clear()
    return {"ok": True, "message": "Conversation history cleared."}


# ── /api/chat/stream（SSE） ───────────────────────────────────
@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """
    流式对话接口。使用 Queue 桥接同步 agent 回调和 SSE 生成器。

    SSE 事件格式（每行 `data: <JSON>\\n\\n`）：
      {"type": "token",      "content": "文字片段"}
      {"type": "tool_start", "tool": "bash_tool", "input": "ls"}
      {"type": "tool_end",   "tool": "bash_tool", "output": "..."}
      {"type": "done"}
      {"type": "error",      "message": "错误信息"}
    """
    event_queue: queue.Queue = queue.Queue()

    def on_token(token: str) -> None:
        event_queue.put({"type": "token", "content": token})

    def on_tool_call(tool, name: str, tool_input: dict) -> None:
        event_queue.put({
            "type": "tool_start",
            "tool": name,
            "input": str(tool_input)[:300],
        })

    def on_tool_result(tool, result) -> None:
        tool_name = getattr(tool, "name", "unknown") if tool else "unknown"
        event_queue.put({
            "type": "tool_end",
            "tool": tool_name,
            "output": (result.content or "")[:500],
        })

    def run_agent() -> None:
        try:
            with _engine_lock:
                engine.submit_message(
                    req.message,
                    on_token=on_token,
                    on_tool_call=on_tool_call,
                    on_tool_result=on_tool_result,
                )
        except Exception as exc:
            event_queue.put({"type": "error", "message": str(exc)})
        finally:
            event_queue.put(None)   # 哨兵：流结束

    threading.Thread(target=run_agent, daemon=True).start()

    def generate() -> Generator[str, None, None]:
        while True:
            event = event_queue.get()
            if event is None:
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── 静态文件服务（生产模式） ─────────────────────────────────
import os
from fastapi.staticfiles import StaticFiles

_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="static")


# ── 入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("web_server:app", host=args.host, port=args.port, reload=args.reload)
