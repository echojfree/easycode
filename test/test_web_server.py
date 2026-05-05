import json
import pytest
from fastapi.testclient import TestClient


def test_health_returns_ok():
    from web_server import app
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "model" in body
    assert "host" in body


def test_health_content_type():
    from web_server import app
    client = TestClient(app)
    resp = client.get("/api/health")
    assert "application/json" in resp.headers["content-type"]


from unittest.mock import patch


def test_clear_returns_ok():
    from web_server import app
    client = TestClient(app)
    resp = client.post("/api/clear")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_chat_stream_event_format():
    """验证 SSE 流中每个事件都是合法 JSON，且最后一个是 done"""
    from web_server import app, engine

    # Mock submit_message：直接调用 on_token 两次然后返回
    def fake_submit(msg, on_token=None, on_tool_call=None, on_tool_result=None, **_):
        if on_token:
            on_token("Hello")
            on_token(" world")

    with patch.object(engine, "submit_message", side_effect=fake_submit):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            raw = resp.read().decode()

    lines = [l for l in raw.split("\n") if l.startswith("data: ")]
    events = [json.loads(l[6:]) for l in lines]

    assert events[0] == {"type": "token", "content": "Hello"}
    assert events[1] == {"type": "token", "content": " world"}
    assert events[-1] == {"type": "done"}


def test_chat_stream_tool_events():
    """验证 tool_start / tool_end 事件格式"""
    from web_server import app, engine
    from scc.types import ToolResult

    class FakeTool:
        name = "bash_tool"

    def fake_submit(msg, on_token=None, on_tool_call=None, on_tool_result=None, **_):
        if on_tool_call:
            on_tool_call(FakeTool(), "bash_tool", {"command": "ls"})
        if on_tool_result:
            on_tool_result(FakeTool(), ToolResult(content="file1.txt\nfile2.txt"))

    with patch.object(engine, "submit_message", side_effect=fake_submit):
        client = TestClient(app)
        with client.stream("POST", "/api/chat/stream", json={"message": "list files"}) as resp:
            raw = resp.read().decode()

    events = [json.loads(l[6:]) for l in raw.split("\n") if l.startswith("data: ")]
    types = [e["type"] for e in events]
    assert "tool_start" in types
    assert "tool_end" in types
    assert "done" in types

    tool_start = next(e for e in events if e["type"] == "tool_start")
    assert tool_start["tool"] == "bash_tool"
