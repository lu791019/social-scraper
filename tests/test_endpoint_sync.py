"""LINE webhook 同步：挑 ngrok 網址、只在不同時 PUT、token 不外洩。"""
import httpx
import pytest

from line_webhook.endpoint_sync import callback_url, pick_public_url, sync_endpoint

TOKEN = "secret-token-xyz"


def test_pick_public_url_matches_port_and_https():
    tunnels = {"tunnels": [
        {"public_url": "http://a.ngrok-free.app", "config": {"addr": "http://localhost:8010"}},
        {"public_url": "https://b.ngrok-free.app", "config": {"addr": "http://localhost:8000"}},
        {"public_url": "https://c.ngrok-free.app", "config": {"addr": "http://localhost:8010"}},
    ]}
    assert pick_public_url(tunnels, 8010) == "https://c.ngrok-free.app"
    assert pick_public_url({"tunnels": []}, 8010) is None


def test_callback_url():
    assert callback_url("https://x.ngrok-free.app/") == "https://x.ngrok-free.app/callback"


def _client(current: str, test_body: dict, status: int = 200, calls: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        if calls is not None:
            calls.append((request.method, request.url.path))
        if status != 200:
            return httpx.Response(status, text="unauthorized")
        if request.method == "GET":
            return httpx.Response(200, json={"endpoint": current, "active": True})
        if request.method == "PUT":
            return httpx.Response(200, json={})
        return httpx.Response(200, json=test_body)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sync_puts_when_endpoint_differs():
    calls: list = []
    ok = {"success": True, "statusCode": 200, "reason": "OK", "detail": "200"}
    result = sync_endpoint("https://new/callback", TOKEN, _client("https://old/callback", ok, calls=calls))
    assert result.changed is True and result.test_success is True
    assert ("PUT", "/v2/bot/channel/webhook/endpoint") in calls
    assert calls[-1] == ("POST", "/v2/bot/channel/webhook/test")


def test_sync_skips_put_when_same():
    calls: list = []
    ok = {"success": True, "statusCode": 200, "reason": "OK"}
    result = sync_endpoint("https://same/callback", TOKEN, _client("https://same/callback", ok, calls=calls))
    assert result.changed is False
    assert not any(m == "PUT" for m, _ in calls)


def test_sync_reports_failed_webhook_test():
    bad = {"success": False, "statusCode": 502, "reason": "ERROR_STATUS_CODE"}
    result = sync_endpoint("https://x/callback", TOKEN, _client("https://x/callback", bad))
    assert result.test_success is False
    assert "502" in result.test_detail


def test_sync_401_explains_token_without_leaking_it():
    with pytest.raises(RuntimeError) as exc:
        sync_endpoint("https://x/callback", TOKEN, _client("", {}, status=401))
    assert "重發" in str(exc.value)
    assert TOKEN not in str(exc.value)
