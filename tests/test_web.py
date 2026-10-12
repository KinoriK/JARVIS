import pytest
from fastapi.testclient import TestClient

from jarvis import web


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DASHBOARD_TOKEN", "secret")
    c = TestClient(web.app)
    c.headers["Authorization"] = "Bearer secret"
    return c


def test_api_requires_token(client):
    assert client.get("/api/tasks", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/tasks", headers={"Authorization": ""}).status_code == 401
    assert client.get("/").status_code == 200  # the page itself is public; data isn't


def test_task_create_patch_and_validation(client):
    t = client.post("/api/tasks", json={"title": "Water plants", "due_date": "2030-01-02"}).json()
    assert t["due_date"] == "2030-01-02"
    assert client.post("/api/tasks", json={"title": "x", "due_date": "soon"}).status_code == 422
    assert client.patch(f"/api/tasks/{t['id']}", json={"due_date": ""}).json()["due_date"] is None
    assert client.patch(f"/api/tasks/{t['id']}", json={"status": "done"}).json()["status"] == "done"
    assert client.get("/api/tasks").json() == []
    assert client.patch("/api/tasks/999", json={"status": "done"}).status_code == 404


def test_google_failure_is_friendly_503(client, monkeypatch):
    def boom(*a):
        raise web.GoogleAuthError("re-auth please")
    monkeypatch.setattr(web.gmail, "needs_reply", boom)
    r = client.get("/api/inbox/needs-reply")
    assert r.status_code == 503 and r.json()["detail"] == "re-auth please"


def test_binds_localhost_only():
    assert web.HOST == "127.0.0.1"
