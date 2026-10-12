"""pipeline：Sheet 寫在處理成功之後；Discord 失敗附註；最終錯誤才寫錯誤列。"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import ProcessedPost
from services import pipeline
from services.summarizer import PostSummary

_PROCESSED = ProcessedPost(url="https://www.threads.com/@a/post/X", platform="threads", author="a",
                           first_image=None, summary=PostSummary("摘要", "• 一", "T", "嘶～"), warnings=("圖片 OCR失敗",))


@pytest.mark.asyncio
@pytest.mark.parametrize("discord_ok", [True, False])
async def test_process_social(discord_ok):
    with patch("scraper.browser.create_browser", AsyncMock(return_value=(MagicMock(), MagicMock()))), \
         patch("scraper.browser.close_browser", AsyncMock()), \
         patch("main.process_post_detailed", AsyncMock(return_value=_PROCESSED)), \
         patch("services.sheet.append_url", return_value=12) as append, \
         patch("services.sheet.write_result") as write, \
         patch("services.discord_sink.send_post_to_discord", AsyncMock(return_value=discord_ok)):
        out = await pipeline.process_social(_PROCESSED.url)
    append.assert_called_once_with(_PROCESSED.url)
    write.assert_called_once_with(12, "摘要", "• 一")
    assert "第 12 列" in out.message and "圖片 OCR失敗" in out.message
    assert ("Discord 未送出" in out.message) is (not discord_ok)
    assert out.result["discord_sent"] is discord_ok


@pytest.mark.asyncio
async def test_process_social_failure_writes_nothing():
    with patch("scraper.browser.create_browser", AsyncMock(return_value=(MagicMock(), MagicMock()))), \
         patch("scraper.browser.close_browser", AsyncMock()) as close, \
         patch("main.process_post_detailed", AsyncMock(side_effect=RuntimeError("x"))), \
         patch("services.sheet.append_url") as append:
        with pytest.raises(RuntimeError):
            await pipeline.process_social(_PROCESSED.url)
    append.assert_not_called()
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_job_unknown_platform():
    with pytest.raises(ValueError):
        await pipeline.run_job("tiktok", "https://x")


def test_record_final_error_social_and_github():
    with patch("services.sheet.append_url", return_value=5), patch("services.sheet.write_error") as we:
        pipeline.record_final_error("threads", "u", "boom")
    we.assert_called_once_with(5, "boom")
    with patch("services.sheet.append_github_repo", return_value=6), patch("services.sheet.write_github_error") as wge:
        pipeline.record_final_error("github", "u", "boom")
    wge.assert_called_once_with(6, "boom")


def test_record_final_error_swallows_sheet_failure():
    with patch("services.sheet.append_url", side_effect=RuntimeError("sheet down")):
        pipeline.record_final_error("instagram", "u", "boom")  # 不拋
