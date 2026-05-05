"""
embedding_client.py — OpenAI-compatible 向量嵌入客户端
======================================================
当前配置：阿里云 text-embedding-v4（1024 维）

用途：语义搜索、RAG（检索增强生成）、相似度计算
API：POST /embeddings（OpenAI 标准格式）
"""

from __future__ import annotations

import os
from typing import Union

import requests

from .api import APIError


EMBEDDING_API_KEY  = os.environ.get("EMBEDDING_API_KEY", "")
EMBEDDING_BASE_URL = os.environ.get("EMBEDDING_BASE_URL", "")
EMBEDDING_MODEL    = os.environ.get("EMBEDDING_MODEL", "text-embedding-v4")
EMBEDDING_SIZE     = int(os.environ.get("EMBEDDING_SIZE", "1024"))
EMBEDDING_TIMEOUT  = int(os.environ.get("EMBEDDING_TIMEOUT", "30"))


class EmbeddingClient:
    """
    OpenAI-compatible 向量嵌入客户端。

    embed(texts) → list[list[float]]
      返回每段文本的嵌入向量，维度由 EMBEDDING_SIZE 决定。
    """

    def __init__(
        self,
        api_key:  str = EMBEDDING_API_KEY,
        base_url: str = EMBEDDING_BASE_URL,
        model:    str = EMBEDDING_MODEL,
        timeout:  int = EMBEDDING_TIMEOUT,
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

    def embed(
        self,
        texts: Union[str, list[str]],
        dimensions: int = EMBEDDING_SIZE,
    ) -> list[list[float]]:
        """
        获取文本的嵌入向量。

        texts      — 单个字符串或字符串列表
        dimensions — 输出维度（默认 EMBEDDING_SIZE）
        返回 list[list[float]]，与输入顺序对应。
        """
        if isinstance(texts, str):
            texts = [texts]

        payload: dict = {
            "model": self.model,
            "input": texts,
        }
        if dimensions and dimensions != EMBEDDING_SIZE:
            payload["dimensions"] = dimensions

        try:
            resp = requests.post(
                f"{self.base_url}/embeddings",
                headers=self._headers,
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            # OpenAI 格式: {"data": [{"embedding": [...], "index": 0}, ...]}
            items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
            return [item["embedding"] for item in items]

        except requests.exceptions.ConnectionError:
            raise APIError(f"Cannot connect to {self.base_url}")
        except requests.exceptions.Timeout:
            raise APIError(f"Embedding request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            raise APIError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
        except APIError:
            raise
        except Exception as e:
            raise APIError(f"Unexpected error: {e}")

    def ping(self) -> tuple[bool, int]:
        """
        检查向量服务是否可用，返回 (ok, embedding_size)。
        通过嵌入单个短文本验证。
        """
        try:
            vecs = self.embed("ping")
            if vecs and isinstance(vecs[0], list):
                return True, len(vecs[0])
            return False, 0
        except Exception:
            return False, 0
