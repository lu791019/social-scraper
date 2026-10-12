"""HTTP 層：callback 驗簽與入列、worker 端點的 Bearer 驗證。"""
import base64
import hashlib
import hmac
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SECRET, WORKER_KEY = "chan-secret", "worker-key-123"


@pytest.fixture
def client(store, database_url):
    settings = Settings(database_url=database_url, line_channel_secret=SECRET,
                        line_channel_access_token="tok", worker_key=WORKER_KEY)
    with patch("app.main.reply_text", return_value=True) as reply, \
         TestClient(create_app(settings, store)) as c:
        c.reply = reply
        yield c


def _post_callback(client, payload: dict, secret: str = SECRET):
    body = json.dumps(payload).encode()
    sig = base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    return client.post("/callback", content=body, headers={"X-Line-Signature": sig, "Content-Type": "application/json"})


def _text_event(text: str) -> dict:
    return {"events": [{"type": "message", "replyToken": "rt", "source": {"userId": "U1"},
                        "message": {"type": "text", "text": text}}]}


AUTH = {"Authorization": f"Bearer {WORKER_KEY}"}


def test_callback_rejects_bad_signature(client):
    assert _post_callback(client, _text_event("https://a.com"), secret="wrong").status_code == 400


def test_callback_verify_event_ok(client):
    assert _post_callback(client, {"events": []}).status_code == 200


def test_callback_enqueues_and_replies(client, store):
    resp = _post_callback(client, _text_event("https://www.threads.com/@a/post/X https://github.com/a/b"))
    assert resp.status_code == 200
    assert store.pending_count() == 2
    reply_msg = client.reply.call_args.args[2]
    assert "收到 2 筆" in reply_msg


def test_callback_without_links_does_not_enqueue(client, store):
    _post_callback(client, _text_event("哈囉"))
    assert store.pending_count() == 0
    assert "請傳送" in client.reply.call_args.args[2]


def test_worker_endpoints_require_bearer(client):
    assert client.post("/jobs/claim").status_code == 401
    assert client.post("/jobs/claim", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/jobs/1/done", json={"success": True}).status_code == 401


def test_claim_and_done_flow(client):
    assert client.post("/jobs/claim", headers=AUTH).status_code == 204
    _post_callback(client, _text_event("https://www.threads.com/@a/post/X"))
    job = client.post("/jobs/claim", headers=AUTH).json()
    assert (job["url"], job["platform"], job["line_user_id"], job["attempts"]) == \
        ("https://www.threads.com/@a/post/X", "threads", "U1", 1)
    done = client.post(f"/jobs/{job['id']}/done", headers=AUTH, json={"success": True, "result": {"t": 1}})
    assert done.json()["status"] == "done" and done.json()["changed"] is True
    again = client.post(f"/jobs/{job['id']}/done", headers=AUTH, json={"success": False, "error": "x"})
    assert again.json()["status"] == "done" and again.json()["changed"] is False
    assert client.post("/jobs/999/done", headers=AUTH, json={"success": True}).status_code == 404
