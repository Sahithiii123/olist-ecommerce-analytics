from fastapi.testclient import TestClient

from olist_agent.api import app


def test_auth_and_health(monkeypatch, tmp_path):
    monkeypatch.setenv("OLIST_API_KEY", "test-secret")
    monkeypatch.setenv("OLIST_OUTPUT_DIR", str(tmp_path))
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"x-api-key": "test-secret"}).status_code == 200
    assert client.post("/ask", json={"question": "hello"},
                       headers={"x-api-key": "test-secret"}).status_code == 503