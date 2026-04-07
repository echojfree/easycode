#!/usr/bin/env python3
"""
main.py — 程序入口
对应 Claude Code: src/entrypoints/ + index.js
"""
import sys
import io
import os

# Windows UTF-8 兼容（统一在入口处处理）
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _load_dotenv() -> None:
    """从 .env 文件加载环境变量（不覆盖已有的环境变量）。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value


_load_dotenv()

from scc.cli import main

if __name__ == "__main__":
    main()
