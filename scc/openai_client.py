"""
openai_client.py — OpenAI-compatible API 客户端
================================================
与 OllamaClient 接口完全一致，可作为 QueryEngine 的 drop-in 替换。

支持任何实现了 OpenAI Chat Completions API 的服务，例如：
  - 小米 mimo    (https://api.xiaomimimo.com/v1)
  - 阿里云百炼   (https://dashscope.aliyuncs.com/compatible-mode/v1)
  - OpenAI 官方  (https://api.openai.com/v1)

SSE 流式格式（OpenAI）：
  data: {"choices":[{"delta":{"content":"tok"},"finish_reason":null}]}
  data: {"choices":[{"delta":{},"finish_reason":"stop"}]}
  data: [DONE]

工具调用 delta（arguments 分多块到达）：
  data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_x","function":{"name":"bash_tool","arguments":""}}]}}]}
  data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\"command\":"}}]}}]}
  data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"ls\"}"}}]}}]}
"""

from __future__ import annotations

import json
import os
from typing import Generator, Optional, Union

import requests

from .api import APIError


# 从环境变量读取配置（web_server.py 已提前调用 _load_dotenv_override）
OPENAI_API_KEY  = os.environ.get("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT  = int(os.environ.get("OPENAI_TIMEOUT", "120"))


class OpenAIClient:
    """
    OpenAI-compatible API 客户端。
    接口与 OllamaClient 完全一致，QueryEngine 无需感知底层差异。

    chat_stream() yields:
        str  — 每个文本 token
        dict — 最终 message {role, content, tool_calls}
    """

    def __init__(
        self,
        api_key:  str = OPENAI_API_KEY,
        base_url: str = OPENAI_BASE_URL,
        model:    str = OPENAI_MODEL,
        timeout:  int = OPENAI_TIMEOUT,
    ):
        self.api_key  = api_key
        self.base_url = base_url.rstrip("/")
        self.model    = model
        self.timeout  = timeout

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
        }

    # ── 流式聊天（与 OllamaClient.chat_stream 接口相同）───────
    def chat_stream(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
    ) -> Generator[Union[str, dict], None, None]:
        """
        调用 OpenAI-compatible /chat/completions（stream=True）。

        Yields:
            str  — 流式文本 token
            dict — 最终 message，格式：
                   {"role": "assistant", "content": "...", "tool_calls": [...]}
                   tool_calls[i]["function"]["arguments"] 是 JSON 字符串，
                   agent.py 中已有 isinstance(raw_args, str) 分支处理。
        """
        payload: dict = {
            "model":    self.model,
            "messages": messages,
            "stream":   True,
        }
        if tools:
            payload["tools"]       = tools
            payload["tool_choice"] = "auto"

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
                stream=True,
            )
            resp.raise_for_status()

            content_parts: list[str] = []
            # index → {id, name, arguments_accumulator}
            tc_acc: dict[int, dict] = {}

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="replace")
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                choice = choices[0]
                delta  = choice.get("delta") or {}

                # ── 文本 token ──────────────────────────────
                token = delta.get("content") or ""
                if token:
                    content_parts.append(token)
                    yield token

                # ── 工具调用 delta 累积 ─────────────────────
                for tc_delta in delta.get("tool_calls") or []:
                    idx = tc_delta.get("index", 0)
                    if idx not in tc_acc:
                        tc_acc[idx] = {"id": "", "name": "", "arguments": ""}
                    acc = tc_acc[idx]
                    if tc_delta.get("id"):
                        acc["id"] = tc_delta["id"]
                    func = tc_delta.get("function") or {}
                    if func.get("name"):
                        acc["name"] += func["name"]
                    if func.get("arguments"):
                        acc["arguments"] += func["arguments"]

            # ── 组装最终 tool_calls（保持与 Ollama 格式兼容）──
            tool_calls = []
            for idx in sorted(tc_acc):
                acc = tc_acc[idx]
                tool_calls.append({
                    "id":   acc["id"],
                    "type": "function",
                    "function": {
                        "name":      acc["name"],
                        "arguments": acc["arguments"],   # JSON 字符串
                    },
                })

            yield {
                "role":       "assistant",
                "content":    "".join(content_parts),
                "tool_calls": tool_calls,
            }

        except requests.exceptions.ConnectionError:
            raise APIError(f"Cannot connect to {self.base_url}")
        except requests.exceptions.Timeout:
            raise APIError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")

    # ── 健康检查（对应 OllamaClient.ping）───────────────────
    def ping(self) -> tuple[bool, list[str]]:
        """
        检查 API 是否可达，返回 (ok, available_models)。
        调用 GET /models 端点（OpenAI 标准）。
        """
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers=self._headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return False, []
            data = resp.json()
            models = [m.get("id", "") for m in (data.get("data") or [])]
            return True, models
        except Exception:
            return False, []
