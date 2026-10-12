import pytest
from main import detect_platform


def test_detect_platform_instagram():
    assert detect_platform("https://www.instagram.com/p/abc123/") == "instagram"
    assert detect_platform("https://instagram.com/reel/abc123/") == "instagram"


def test_detect_platform_threads():
    assert detect_platform("https://www.threads.net/@user/post/abc123") == "threads"


def test_detect_platform_github():
    assert detect_platform("https://github.com/psf/requests") == "github"
    assert detect_platform("https://github.com/langchain-ai/langchain") == "github"


def test_detect_platform_unknown():
    with pytest.raises(ValueError, match="不支援的平台"):
        detect_platform("https://twitter.com/post/123")


# ── process_post_detailed：一次處理，同時供 Sheet 與 Discord 使用 ──

from unittest.mock import AsyncMock, patch  # noqa: E402

from main import process_post, process_post_detailed, to_discord_post  # noqa: E402
from scraper.instagram import PostData  # noqa: E402
from services.summarizer import PostSummary  # noqa: E402

_SUMMARY = PostSummary(summary="摘要", key_points="• 一", title="標題", discord_comment="嘶～")


@pytest.mark.asyncio
async def test_process_post_detailed_collects_metadata():
    post = PostData(caption="文", image_urls=["https://img/1.jpg", "https://img/2.jpg"], author="zuck")
    with patch("main.scrape_threads", AsyncMock(return_value=post)), \
         patch("main.process_images", AsyncMock(return_value="圖字")), \
         patch("main.summarize_post", AsyncMock(return_value=_SUMMARY)):
        result = await process_post_detailed(None, "https://www.threads.com/@zuck/post/X")
    assert result.platform == "threads"
    assert result.author == "zuck"
    assert result.first_image == "https://img/1.jpg"
    assert result.summary is _SUMMARY


@pytest.mark.asyncio
async def test_process_post_keeps_tuple_interface():
    post = PostData(caption="文")
    with patch("main.scrape_instagram", AsyncMock(return_value=post)), \
         patch("main.summarize_post", AsyncMock(return_value=_SUMMARY)):
        assert await process_post(None, "https://www.instagram.com/p/X/") == ("摘要", "• 一")


def test_to_discord_post_maps_fields():
    from main import ProcessedPost
    processed = ProcessedPost(url="u", platform="instagram", author="a", first_image=None, summary=_SUMMARY)
    dp = to_discord_post(processed)
    assert (dp.url, dp.platform, dp.author, dp.title, dp.summary, dp.key_points, dp.comment, dp.image_url) == \
        ("u", "instagram", "a", "標題", "摘要", "• 一", "嘶～", None)


@pytest.mark.asyncio
async def test_media_failure_degrades_with_visible_warning():
    """圖片下載被擋：用貼文文字繼續，但 warnings 要帶出來（不能靜默降級）"""
    post = PostData(caption="文", image_urls=["https://img/1.jpg"], video_url="https://v/1.mp4", author="a")
    summarize = AsyncMock(return_value=_SUMMARY)
    with patch("main.scrape_threads", AsyncMock(return_value=post)), \
         patch("main.process_images", AsyncMock(side_effect=RuntimeError("SSL blocked"))), \
         patch("main.process_video", AsyncMock(side_effect=RuntimeError("ffmpeg"))), \
         patch("main.summarize_post", summarize):
        result = await process_post_detailed(None, "https://www.threads.com/@a/post/X")
    assert result.summary is _SUMMARY
    assert "【貼文文字】" in summarize.call_args.args[0]
    assert len(result.warnings) == 2
    assert "圖片" in result.warnings[0] and "影片" in result.warnings[1]


@pytest.mark.asyncio
async def test_media_failure_without_caption_still_raises():
    """沒有任何文字可摘要時，媒體失敗就整篇失敗"""
    post = PostData(caption="", image_urls=["https://img/1.jpg"])
    with patch("main.scrape_threads", AsyncMock(return_value=post)), \
         patch("main.process_images", AsyncMock(side_effect=RuntimeError("SSL blocked"))):
        with pytest.raises(RuntimeError, match="沒有可摘要的內容"):
            await process_post_detailed(None, "https://www.threads.com/@a/post/X")
