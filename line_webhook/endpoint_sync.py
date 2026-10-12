"""把 LINE webhook 指到目前的 ngrok 公開網址，並呼叫 LINE 的 webhook 測試。

token 只放在 Authorization header，任何 log／錯誤訊息都不輸出 token。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

LINE_API = "https://api.line.me/v2/bot/channel/webhook"
CALLBACK_PATH = "/callback"
INSPECT_POLL_SECONDS = 30
INSPECT_POLL_INTERVAL = 1.0


@dataclass(frozen=True)
class SyncResult:
    endpoint: str
    changed: bool
    test_success: bool
    test_detail: str


def pick_public_url(tunnels: dict, port: int) -> str | None:
    """從 ngrok inspector /api/tunnels 回應挑出指向本機 port 的 https 網址。"""
    for tunnel in tunnels.get("tunnels", []):
        addr = str(tunnel.get("config", {}).get("addr", ""))
        url = str(tunnel.get("public_url", ""))
        if url.startswith("https://") and addr.rstrip("/").endswith(f":{port}"):
            return url
    return None


def callback_url(public_url: str) -> str:
    return public_url.rstrip("/") + CALLBACK_PATH


def wait_for_public_url(inspect_addr: str, port: int, client: httpx.Client,
                        timeout_s: float = INSPECT_POLL_SECONDS) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = client.get(f"http://{inspect_addr}/api/tunnels", timeout=3)
            url = pick_public_url(resp.json(), port)
            if url:
                return url
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(INSPECT_POLL_INTERVAL)
    raise RuntimeError(f"{timeout_s:.0f} 秒內等不到 ngrok 公開網址（inspector {inspect_addr}）")


def _raise_for_line(resp: httpx.Response, action: str) -> None:
    if resp.status_code == 401:
        raise RuntimeError(f"LINE {action} 失敗：401，Channel access token 失效，請到 LINE Developers Console 重發")
    if resp.status_code >= 400:
        raise RuntimeError(f"LINE {action} 失敗：HTTP {resp.status_code} {resp.text[:200]}")


def sync_endpoint(target: str, token: str, client: httpx.Client) -> SyncResult:
    """讀目前 webhook；不同才 PUT；最後一律呼叫 webhook test。"""
    headers = {"Authorization": f"Bearer {token}"}
    current = client.get(f"{LINE_API}/endpoint", headers=headers, timeout=10)
    _raise_for_line(current, "讀取 webhook")
    changed = current.json().get("endpoint") != target
    if changed:
        _raise_for_line(client.put(f"{LINE_API}/endpoint", headers=headers,
                                   json={"endpoint": target}, timeout=10), "設定 webhook")
    test = client.post(f"{LINE_API}/test", headers=headers, json={"endpoint": target}, timeout=30)
    _raise_for_line(test, "webhook 測試")
    body = test.json()
    detail = f"statusCode={body.get('statusCode')} reason={body.get('reason')} {body.get('detail', '')}".strip()
    return SyncResult(endpoint=target, changed=changed, test_success=bool(body.get("success")), test_detail=detail)
