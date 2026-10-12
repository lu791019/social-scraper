"""Discord 出口：IG/Threads 處理完成後，以「蛇摸影評」身分發 embed 到 webhook。

失敗只記 log 並回傳 False，不拋例外——不能影響 Sheet 寫入與 LINE 回覆。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from config import DISCORD_SNAKE_AVATAR, DISCORD_WEBHOOK_URL

logger = logging.getLogger(__name__)

SNAKE_USERNAME = "蛇摸影評"
EMBED_COLOR = 0x2E8B57  # 蛇綠
MAX_KEY_POINTS = 5
REQUEST_TIMEOUT_S = 15

# Discord embed 長度上限
TITLE_LIMIT = 256
DESCRIPTION_LIMIT = 4096
FIELD_VALUE_LIMIT = 1024
AUTHOR_LIMIT = 256

PLATFORM_LABELS = {"threads": "Threads", "instagram": "Instagram"}
_BULLET_RE = re.compile(r"^\s*(?:[•\-\*·]|\d+[.)、])\s*")


@dataclass(frozen=True)
class DiscordPost:
    url: str
    platform: str
    author: str
    title: str
    summary: str
    key_points: str
    comment: str
    image_url: str | None = None


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def split_key_points(key_points: str) -> list[str]:
    """把「• 」開頭的多行關鍵點拆成清單，去掉項目符號，最多取 5 個。"""
    lines = (_BULLET_RE.sub("", line).strip() for line in key_points.splitlines())
    return [line for line in lines if line][:MAX_KEY_POINTS]


def _platform_label(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform or "社群")


def _fallback_title(post: DiscordPost) -> str:
    label = _platform_label(post.platform)
    return f"@{post.author} 的 {label} 貼文" if post.author else f"{label} 貼文"


def build_payload(post: DiscordPost, avatar_url: str) -> dict:
    """組 webhook payload（純函式，方便測試）。"""
    label = _platform_label(post.platform)
    author_name = f"{label} · @{post.author}" if post.author else label
    description = "\n\n".join(p for p in (post.comment.strip(), post.summary.strip()) if p)

    points = split_key_points(post.key_points)
    point_lines = [f"• {_truncate(p, 200)}" for p in points]
    fields = [{"name": "重點", "value": _truncate("\n".join(point_lines), FIELD_VALUE_LIMIT), "inline": False}] if points else []

    embed: dict = {
        "title": _truncate(post.title.strip() or _fallback_title(post), TITLE_LIMIT),
        "url": post.url,
        "description": _truncate(description, DESCRIPTION_LIMIT),
        "color": EMBED_COLOR,
        "author": {"name": _truncate(author_name, AUTHOR_LIMIT)},
        "fields": fields,
        "footer": {"text": "社群剪報 · LINE → social-scraper"},
    }
    if post.image_url:
        embed["image"] = {"url": post.image_url}

    payload: dict = {
        "username": SNAKE_USERNAME,
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
    }
    if avatar_url:
        payload["avatar_url"] = avatar_url
    return payload


async def send_post_to_discord(
    post: DiscordPost,
    webhook_url: str | None = None,
    avatar_url: str | None = None,
) -> bool:
    """發送到 Discord webhook。成功回 True；未設定或失敗回 False（只記 log）。"""
    url = DISCORD_WEBHOOK_URL if webhook_url is None else webhook_url
    avatar = DISCORD_SNAKE_AVATAR if avatar_url is None else avatar_url
    if not url:
        logger.warning("Discord 出口未設定 DISCORD_WEBHOOK_URL，略過發送")
        return False

    payload = build_payload(post, avatar)
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            response = await client.post(url, params={"wait": "true"}, json=payload)
        if response.status_code >= 400:
            logger.error(f"Discord 發送失敗：HTTP {response.status_code} {response.text[:200]}（{post.url}）")
            return False
    except httpx.HTTPError as e:
        logger.error(f"Discord 發送失敗：{type(e).__name__}（{post.url}）")
        return False
    logger.info(f"Discord 已發送：{post.url}")
    return True
