"""LINE push（Mac 工作程式回報結果）。失敗只記 log、回 False。"""
from __future__ import annotations

import logging

import httpx

from config import LINE_CHANNEL_ACCESS_TOKEN

logger = logging.getLogger(__name__)
PUSH_API = "https://api.line.me/v2/bot/message/push"
LINE_TEXT_LIMIT = 5000


def push_text(user_id: str | None, text: str, token: str | None = None) -> bool:
    if not user_id:
        logger.warning("沒有 LINE user id，略過推播")
        return False
    try:
        resp = httpx.post(
            PUSH_API,
            headers={"Authorization": f"Bearer {token or LINE_CHANNEL_ACCESS_TOKEN}"},
            json={"to": user_id, "messages": [{"type": "text", "text": text[:LINE_TEXT_LIMIT]}]},
            timeout=10,
        )
    except httpx.HTTPError as e:
        logger.error(f"LINE push 失敗：{type(e).__name__}")
        return False
    if resp.status_code >= 400:
        logger.error(f"LINE push 失敗：HTTP {resp.status_code} {resp.text[:200]}")
        return False
    return True
