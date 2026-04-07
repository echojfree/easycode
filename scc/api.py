"""
api.py — LLM API 客户端
========================
对应 Claude Code 源码:
  src/services/api/claude.ts → queryModelWithStreaming()

Claude Code 的 API 层职责:
  - 向 Anthropic API 发送流式请求
  - 处理 BetaRawMessageStreamEvent（content_block_delta 等）
  - 管理重试逻辑（withRetry）
  - Token 用量统计（accumulateUsage）
  - 工具 Schema 转换（toolToAPISchema）

本实现对应 Ollama /api/chat，使用非流式请求（简化版）。
后续可扩展为流式以实现实时输出。
"""

from __future__ import annotations
from typing import Generator, Optional, Union
import json
import os
import requests

# Ollama 配置（优先读取环境变量，回退到默认值）
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "10.100.11.245")
OLLAMA_PORT = int(os.environ.get("OLLAMA_PORT", "11434"))
MODEL       = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")
TIMEOUT_S   = int(os.environ.get("OLLAMA_TIMEOUT", "180"))
API_URL     = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api/chat"


class APIError(Exception):
    """API 调用失败"""


class OllamaClient:
    """
    Ollama API 客户端。
    对应 Claude Code: services/api/claude.ts 中的 API 调用逻辑。

    Ollama /api/chat 与 OpenAI Chat Completions API 格式兼容:
      POST /api/chat
      {
        "model": "...",
        "messages": [...],
        "tools": [...],    # 可选，触发工具调用
        "stream": false
      }
    """

    def __init__(
        self,
        host: str = OLLAMA_HOST,
        port: int = OLLAMA_PORT,
        model: str = MODEL,
        timeout: int = TIMEOUT_S,
    ):
        self.base_url = f"http://{host}:{port}"
        self.model    = model
        self.timeout  = timeout

    # ── 核心：发送一次聊天请求 ─────────────────────────────
    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> dict:
        """
        向 LLM 发送消息，返回 message 对象。

        对应 Claude Code: queryModelWithStreaming()
        这里简化为非流式请求，返回格式:
          {
            "role": "assistant",
            "content": "...",       # 纯文本回复（可能为空）
            "tool_calls": [...]     # 工具调用列表（可能为空）
          }

        Claude Code 的消息会经过 normalizeMessagesForAPI() 处理，
        这里假设消息已是正确格式。
        """
        payload: dict = {
            "model":   self.model,
            "messages": messages,
            "stream":  False,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {})

        except requests.exceptions.ConnectionError:
            raise APIError(
                f"Cannot connect to Ollama at {self.base_url}\n"
                "Please ensure Ollama is running."
            )
        except requests.exceptions.Timeout:
            raise APIError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP error: {e}")
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")

    # ── 流式请求 ────────────────────────────────────────────
    def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> Generator[Union[str, dict], None, None]:
        """
        流式聊天请求。

        Yields:
            str  — 每个文本 token（LLM 边生成边 yield）
            dict — 最终 message，格式同 chat() 返回值，含 content 全文和 tool_calls
                   （流结束时作为最后一次 yield）

        对应 Claude Code: queryModelWithStreaming() → AsyncGenerator<StreamEvent>
        """
        payload: dict = {
            "model":    self.model,
            "messages": messages,
            "stream":   True,
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            collected: list[str] = []
            pending_tool_calls: list = []   # 从任意 chunk 累积工具调用

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                chunk = json.loads(raw_line.decode("utf-8"))
                msg   = chunk.get("message", {})
                token = msg.get("content") or ""
                tc    = msg.get("tool_calls")

                if token:
                    collected.append(token)
                    yield token                              # ← 文本 token

                # Ollama 可能在任意 chunk（非 done）中携带 tool_calls，
                # 例如 gemma4 在最后一个非 done chunk 中发送工具调用，
                # done chunk 的 tool_calls 反而是 None。
                if tc:
                    pending_tool_calls = tc

                if chunk.get("done"):
                    # done chunk 的 tool_calls 优先（兼容其他模型）
                    done_tc = msg.get("tool_calls")
                    if done_tc:
                        pending_tool_calls = done_tc
                    yield {                                  # ← 最终 message
                        "role":       "assistant",
                        "content":    "".join(collected),
                        "tool_calls": pending_tool_calls,
                    }
                    return

        except requests.exceptions.ConnectionError:
            raise APIError(
                f"Cannot connect to Ollama at {self.base_url}\n"
                "Please ensure Ollama is running."
            )
        except requests.exceptions.Timeout:
            raise APIError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP error: {e}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")

    # ── 健康检查 ────────────────────────────────────────────
    def ping(self) -> tuple[bool, list[str]]:
        """
        检查 Ollama 服务和模型是否就绪。
        返回 (ok, available_models)
        """
        try:
            resp = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            if resp.status_code != 200:
                return False, []
            models = [m["name"] for m in resp.json().get("models", [])]
            return True, models
        except Exception:
            return False, []
