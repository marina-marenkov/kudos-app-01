import asyncio
import importlib
import json

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def api_module(monkeypatch, tmp_path):
    monkeypatch.setenv("KUDOS_DB_PATH", str(tmp_path / "test_kudos.db"))
    import src.api as api

    return importlib.reload(api)


@pytest.fixture
def client(api_module):
    with TestClient(api_module.app) as test_client:
        yield test_client


def _post_kudos_async(app, payload):
    async def _run():
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            return await ac.post("/kudos", json=payload)

    return asyncio.run(_run())


def test_create_kudos(api_module):
    response = _post_kudos_async(
        api_module.app,
        {
            "from_user": "alice",
            "to_user": "bob",
            "message": "Great review!",
            "category": "teamwork",
        },
    )

    assert response.status_code == 201
    payload = response.json()["kudos"]
    assert payload["id"] > 0
    assert payload["from_user"] == "alice"
    assert payload["to_user"] == "bob"
    assert payload["message"] == "Great review!"
    assert payload["category"] == "teamwork"


def test_create_kudos_sends_webhook(monkeypatch, api_module):
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")
    captured: dict[str, object] = {}

    class _MockResponse:
        def close(self):
            return None

    def mock_urlopen(req, timeout):
        captured["request"] = req
        captured["timeout"] = timeout
        return _MockResponse()

    monkeypatch.setattr(api_module.request, "urlopen", mock_urlopen)

    response = _post_kudos_async(
        api_module.app,
        {
            "from_user": "alice",
            "to_user": "bob",
            "message": "Great review!",
            "category": "teamwork",
        },
    )

    assert response.status_code == 201
    request_obj = captured["request"]
    assert request_obj.full_url == "https://example.com/webhook"
    assert request_obj.get_method() == "POST"
    assert captured["timeout"] == 5
    webhook_payload = json.loads(request_obj.data.decode("utf-8"))
    facts = webhook_payload["sections"][0]["facts"]
    assert facts == [
        {"name": "Sender", "value": "alice"},
        {"name": "Receiver", "value": "bob"},
        {"name": "Category", "value": "teamwork"},
        {"name": "Message", "value": "Great review!"},
    ]


def test_create_kudos_without_webhook_url_does_not_send_webhook(monkeypatch, api_module):
    monkeypatch.delenv("WEBHOOK_URL", raising=False)

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("Webhook sender should not be called")

    monkeypatch.setattr(api_module.request, "urlopen", fail_urlopen)

    response = _post_kudos_async(
        api_module.app,
        {
            "from_user": "alice",
            "to_user": "bob",
            "message": "Great review!",
            "category": "teamwork",
        },
    )

    assert response.status_code == 201


def test_create_kudos_webhook_failure_does_not_fail_request(monkeypatch, api_module):
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com/webhook")

    def fail_urlopen(*_args, **_kwargs):
        raise RuntimeError("webhook unavailable")

    monkeypatch.setattr(api_module.request, "urlopen", fail_urlopen)

    response = _post_kudos_async(
        api_module.app,
        {
            "from_user": "alice",
            "to_user": "bob",
            "message": "Great review!",
            "category": "teamwork",
        },
    )

    assert response.status_code == 201


def test_get_leaderboard(client):
    client.post(
        "/kudos",
        json={
            "from_user": "alice",
            "to_user": "bob",
            "message": "Nice!",
            "category": "teamwork",
        },
    )
    client.post(
        "/kudos",
        json={
            "from_user": "carol",
            "to_user": "bob",
            "message": "Thanks!",
            "category": "help",
        },
    )
    client.post(
        "/kudos",
        json={
            "from_user": "dave",
            "to_user": "alice",
            "message": "Great help",
            "category": "support",
        },
    )

    response = client.get("/leaderboard")
    assert response.status_code == 200
    assert response.json() == {
        "leaderboard": [
            {"to_user": "bob", "kudos_count": 2},
            {"to_user": "alice", "kudos_count": 1},
        ]
    }


def test_get_user_kudos(client):
    client.post(
        "/kudos",
        json={
            "from_user": "alice",
            "to_user": "bob",
            "message": "Great teamwork",
            "category": "teamwork",
        },
    )
    client.post(
        "/kudos",
        json={
            "from_user": "carol",
            "to_user": "bob",
            "message": "Awesome support",
            "category": "support",
        },
    )

    response = client.get("/kudos/bob")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"] == "bob"
    assert len(payload["kudos"]) == 2
    assert {item["from_user"] for item in payload["kudos"]} == {"alice", "carol"}
    assert all(item["to_user"] == "bob" for item in payload["kudos"])


def test_invalid_input_returns_422(api_module):
    response = _post_kudos_async(
        api_module.app,
        {
            "from_user": "",
            "to_user": "bob",
            "message": "",
            "category": "",
        },
    )

    assert response.status_code == 422
