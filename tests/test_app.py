"""LINE webhook 背景任務：Discord 出口失敗不能影響 Sheet 與 LINE。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from line_webhook import app as app_module
from main import ProcessedPost
from services.summarizer import PostSummary

_RESULT = ProcessedPost(
    url="https://www.threads.com/@a/post/X", platform="threads", author="a", first_image=None,
    summary=PostSummary(summary="摘要", key_points="• 一", title="T", discord_comment="嘶～"),
)


def test_health_endpoint():
    resp = TestClient(app_module.app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("discord_ok", [True, False])
async def test_scraper_writes_sheet_and_pushes_regardless_of_discord(discord_ok):
    pushed: list[str] = []
    with patch("scraper.browser.create_browser", AsyncMock(return_value=(MagicMock(), MagicMock()))), \
         patch("scraper.browser.close_browser", AsyncMock()), \
         patch("main.process_post_detailed", AsyncMock(return_value=_RESULT)), \
         patch("services.sheet.write_result") as write_result, \
         patch("services.discord_sink.send_post_to_discord", AsyncMock(return_value=discord_ok)) as send, \
         patch.object(app_module, "push_text", side_effect=lambda uid, text: pushed.append(text)):
        await app_module.run_scraper_for_url("U1", _RESULT.url, 7)

    write_result.assert_called_once_with(7, "摘要", "• 一")
    send.assert_awaited_once()
    assert "✅ 第 7 列完成" in pushed[-1]
    assert ("Discord 未送出" in pushed[-1]) is (not discord_ok)
    assert app_module._running == 0
