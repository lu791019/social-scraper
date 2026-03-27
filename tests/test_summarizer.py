import pytest
from unittest.mock import patch
from services.summarizer import (
    summarize_and_extract,
    format_raw_content,
    _parse_summary_and_key_points,
)


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


def test_parse_summary_and_key_points_normal():
    """Scenario: 標準格式回應"""
    text = "【摘要】\n這是摘要內容。\n\n【關鍵點】\n• 重點一\n• 重點二\n• 重點三"
    summary, key_points = _parse_summary_and_key_points(text)
    assert summary == "這是摘要內容。"
    assert "• 重點一" in key_points
    assert key_points.count("•") == 3


def test_parse_summary_and_key_points_no_markers():
    """Scenario: LLM 沒按格式回 → 全部當摘要"""
    text = "這只是一段普通文字"
    summary, key_points = _parse_summary_and_key_points(text)
    assert summary == "這只是一段普通文字"
    assert key_points == ""


def test_parse_summary_and_key_points_only_summary():
    """Scenario: 只有摘要標記，沒有關鍵點"""
    text = "【摘要】\n這是摘要"
    summary, key_points = _parse_summary_and_key_points(text)
    assert summary == "這是摘要"
    assert key_points == ""


@pytest.mark.asyncio
@patch("services.summarizer.run_claude_print")
async def test_summarize_and_extract_returns_tuple(mock_run):
    """Scenario: claude --print 一次回傳摘要+關鍵點"""
    mock_run.return_value = "【摘要】\n這是 AI 摘要\n\n【關鍵點】\n• 重點一\n• 重點二\n• 重點三"
    summary, key_points = await summarize_and_extract("一些原始內容")
    assert summary == "這是 AI 摘要"
    assert "• 重點一" in key_points
    mock_run.assert_called_once()
