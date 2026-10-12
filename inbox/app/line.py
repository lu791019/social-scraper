"""LINE：簽章驗證、連結抽取與分類、reply。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re

import httpx

logger = logging.getLogger(__name__)

REPLY_API = "https://api.line.me/v2/bot/message/reply"
MAX_URLS_PER_MESSAGE = 10

# 只取可列印 ASCII：LINE 訊息常見「連結。中文」直接相連
_URL_RE = re.compile(r"https?://[!-~]+")
_SOCIAL_RE = re.compile(r"^https?://(?:www\.)?(instagram\.com|threads\.net|threads\.com)/", re.I)
_GITHUB_RE = re.compile(r"^https?://github\.com/[^/\s]+/[^/\s#?]+", re.I)


def verify_signature(channel_secret: str, body: bytes, signature: str) -> bool:
    """X-Line-Signature = base64(HMAC-SHA256(channel_secret, body))"""
    if not signature or not channel_secret:
        return False
    digest = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def classify(url: str) -> str:
    match = _SOCIAL_RE.match(url)
    if match:
        return "instagram" if match.group(1).lower() == "instagram.com" else "threads"
    if _GITHUB_RE.match(url):
        return "github"
    return "article"


def extract_links(text: str) -> list[tuple[str, str]]:
    """回傳 [(url, platform)]，去重、保留順序、最多 10 筆。"""
    seen: dict[str, str] = {}
    for raw in _URL_RE.findall(text):
        url = raw.rstrip(".,;!?)]>\"'")
        if url not in seen:
            seen[url] = classify(url)
    return list(seen.items())[:MAX_URLS_PER_MESSAGE]


def reply_text(token: str, reply_token: str, text: str) -> bool:
    """回覆失敗只記 log（reply token 30 秒內有效，失敗也不影響已入列的工作）。"""
    try:
        resp = httpx.post(
            REPLY_API,
            headers={"Authorization": f"Bearer {token}"},
            json={"replyToken": reply_token, "messages": [{"type": "text", "text": text[:5000]}]},
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.error(f"LINE reply 失敗：HTTP {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except httpx.HTTPError as e:
        logger.error(f"LINE reply 失敗：{type(e).__name__}")
        return False
