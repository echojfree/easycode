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
