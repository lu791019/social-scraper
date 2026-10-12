"""Discord sink 單元測試：embed 組裝 + webhook 發送（mock httpx）。"""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from services.discord_sink import (
    DiscordPost,
    build_payload,
    send_post_to_discord,
    split_key_points,
    SNAKE_USERNAME,
)


def _post(**overrides) -> DiscordPost:
    base = dict(
        url="https://www.threads.com/@someone/post/ABC123",
        platform="threads",
        author="someone",
        title="AI 工具整理",
        summary="這篇整理了三個 AI 工具。適合想自動化的人。",
        key_points="• 重點一\n• 重點二\n• 重點三\n• 重點四\n• 重點五\n• 重點六",
        comment="嘶～這幾個工具我先收進洞裡了",
        image_url="https://cdn.example.com/a.jpg",
    )
    base.update(overrides)
    return DiscordPost(**base)


def test_split_key_points_caps_at_five_and_strips_bullets():
    points = split_key_points("• 一\n• 二\n\n- 三\n1. 四\n• 五\n• 六")
    assert points == ["一", "二", "三", "四", "五"]


def test_split_key_points_empty():
    assert split_key_points("") == []


def test_build_payload_uses_snake_identity_and_avatar():
    payload = build_payload(_post(), avatar_url="https://cdn.example.com/snake.png")
    assert payload["username"] == SNAKE_USERNAME == "蛇摸影評"
    assert payload["avatar_url"] == "https://cdn.example.com/snake.png"
    assert payload["allowed_mentions"] == {"parse": []}


def test_build_payload_embed_fields():
    embed = build_payload(_post(), avatar_url="")["embeds"][0]
    assert embed["title"] == "AI 工具整理"
    assert embed["url"] == "https://www.threads.com/@someone/post/ABC123"
    assert "嘶～這幾個工具我先收進洞裡了" in embed["description"]
    assert "這篇整理了三個 AI 工具" in embed["description"]
    assert embed["author"]["name"] == "Threads · @someone"
    assert embed["image"] == {"url": "https://cdn.example.com/a.jpg"}
    points_field = next(f for f in embed["fields"] if f["name"] == "重點")
    assert points_field["value"].count("\n") == 4  # 5 行
    assert "重點六" not in points_field["value"]


def test_build_payload_without_avatar_or_image():
    payload = build_payload(_post(image_url=None, author=""), avatar_url="")
    embed = payload["embeds"][0]
    assert "avatar_url" not in payload
    assert "image" not in embed
    assert embed["author"]["name"] == "Threads"


def test_build_payload_truncates_to_discord_limits():
    long = "字" * 5000
    embed = build_payload(_post(title=long, summary=long, key_points="• " + long), avatar_url="")["embeds"][0]
    assert len(embed["title"]) <= 256
    assert len(embed["description"]) <= 4096
    assert all(len(f["value"]) <= 1024 for f in embed["fields"])


def test_build_payload_falls_back_title_when_empty():
    embed = build_payload(_post(title="", platform="instagram", author="cat"), avatar_url="")["embeds"][0]
    assert embed["title"] == "@cat 的 Instagram 貼文"


def _mock_client(response=None, exc=None):
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    if exc:
        client.post = AsyncMock(side_effect=exc)
    else:
        client.post = AsyncMock(return_value=response)
    return client


@pytest.mark.asyncio
async def test_send_posts_to_webhook_with_wait():
    resp = httpx.Response(200, request=httpx.Request("POST", "https://discord.test/x"))
    client = _mock_client(response=resp)
    with patch("services.discord_sink.httpx.AsyncClient", return_value=client):
        ok = await send_post_to_discord(_post(), webhook_url="https://discord.test/x", avatar_url="")
    assert ok is True
    args, kwargs = client.post.call_args
    assert args[0] == "https://discord.test/x"
    assert kwargs["params"] == {"wait": "true"}
    assert kwargs["json"]["username"] == "蛇摸影評"


@pytest.mark.asyncio
async def test_send_returns_false_on_http_error(caplog):
    resp = httpx.Response(400, text="bad", request=httpx.Request("POST", "https://discord.test/x"))
    client = _mock_client(response=resp)
    with patch("services.discord_sink.httpx.AsyncClient", return_value=client):
        ok = await send_post_to_discord(_post(), webhook_url="https://discord.test/x", avatar_url="")
    assert ok is False
    assert "Discord" in caplog.text
    assert "discord.test/x" not in caplog.text  # 不洩漏 webhook URL


@pytest.mark.asyncio
async def test_send_returns_false_on_network_error():
    client = _mock_client(exc=httpx.ConnectError("boom"))
    with patch("services.discord_sink.httpx.AsyncClient", return_value=client):
        ok = await send_post_to_discord(_post(), webhook_url="https://discord.test/x", avatar_url="")
    assert ok is False


@pytest.mark.asyncio
async def test_send_skips_when_webhook_not_configured():
    with patch("services.discord_sink.httpx.AsyncClient") as client_cls:
        ok = await send_post_to_discord(_post(), webhook_url="", avatar_url="")
    assert ok is False
    client_cls.assert_not_called()
