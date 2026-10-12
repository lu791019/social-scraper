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


# ── Discord 點評欄位（新增段落不能污染 Sheet 的摘要/關鍵點）──

from services.summarizer import PostSummary, summarize_post, _parse_post_summary  # noqa: E402

FULL_RESPONSE = (
    "【摘要】\n這是摘要。\n\n"
    "【關鍵點】\n• 重點一\n• 重點二\n\n"
    "【Discord標題】\nAI 工具三連發\n\n"
    "【Discord點評】\n嘶～這三個工具我先叼回洞裡，第二個最實用。"
)


def test_parse_post_summary_extracts_discord_sections():
    result = _parse_post_summary(FULL_RESPONSE)
    assert result == PostSummary(
        summary="這是摘要。",
        key_points="• 重點一\n• 重點二",
        title="AI 工具三連發",
        discord_comment="嘶～這三個工具我先叼回洞裡，第二個最實用。",
    )


def test_parse_summary_and_key_points_ignores_discord_sections():
    """Sheet 用的舊 parser：關鍵點不能混進 Discord 段落"""
    summary, key_points = _parse_summary_and_key_points(FULL_RESPONSE)
    assert summary == "這是摘要。"
    assert key_points == "• 重點一\n• 重點二"
    assert "嘶" not in key_points
    assert "Discord" not in key_points


def test_parse_post_summary_without_discord_sections():
    result = _parse_post_summary("【摘要】\n摘要\n\n【關鍵點】\n• 一")
    assert result.summary == "摘要"
    assert result.key_points == "• 一"
    assert result.title == ""
    assert result.discord_comment == ""


def test_parse_post_summary_discord_sections_in_any_order():
    text = "【摘要】\n摘要\n\n【關鍵點】\n• 一\n\n【Discord點評】\n嘶～\n\n【Discord標題】\n標題"
    result = _parse_post_summary(text)
    assert result.key_points == "• 一"
    assert result.title == "標題"
    assert result.discord_comment == "嘶～"


@pytest.mark.asyncio
@patch("services.summarizer.run_claude_print")
async def test_summarize_post_prompt_asks_snake_comment(mock_run):
    mock_run.return_value = FULL_RESPONSE
    result = await summarize_post("原始內容")
    prompt = mock_run.call_args.args[0]
    assert "【Discord點評】" in prompt
    assert "嘶～" in prompt
    assert "【Discord標題】" in prompt
    assert result.discord_comment.startswith("嘶～")


@pytest.mark.asyncio
@patch("services.summarizer.run_claude_print")
async def test_summarize_and_extract_keeps_sheet_fields_clean(mock_run):
    mock_run.return_value = FULL_RESPONSE
    summary, key_points = await summarize_and_extract("原始內容")
    assert summary == "這是摘要。"
    assert key_points == "• 重點一\n• 重點二"
