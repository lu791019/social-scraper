import pytest
from unittest.mock import patch
from services.summarizer import summarize, format_raw_content


def test_format_raw_content_with_all_fields():
    """Scenario: 三個欄位都有值 → 三段標記"""
    result = format_raw_content(
        caption="這是貼文",
        ocr_text="圖片文字",
        transcript="影片逐字稿",
    )
    assert "【貼文文字】" in result
    assert "這是貼文" in result
    assert "【圖片文字】" in result
    assert "圖片文字" in result
    assert "【影片逐字稿】" in result
    assert "影片逐字稿" in result


def test_format_raw_content_omits_empty_fields():
    """Scenario: 只有 caption → 只有一段標記"""
    result = format_raw_content(caption="只有文字", ocr_text="", transcript="")
    assert "【貼文文字】" in result
    assert "【圖片文字】" not in result
    assert "【影片逐字稿】" not in result


def test_format_raw_content_empty_caption():
    """Scenario: 只有 OCR → caption 省略"""
    result = format_raw_content(caption="", ocr_text="圖片文字", transcript="")
    assert "【貼文文字】" not in result
    assert "【圖片文字】" in result


@pytest.mark.asyncio
@patch("services.summarizer.run_claude_print")
async def test_summarize_returns_text(mock_run):
    """Scenario: claude --print 回傳摘要"""
    mock_run.return_value = "這是 AI 摘要"
    result = await summarize("一些原始內容")
    assert result == "這是 AI 摘要"
