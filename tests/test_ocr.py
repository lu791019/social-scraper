import pytest
from pathlib import Path
from unittest.mock import patch
from media.ocr import extract_image_text, format_ocr_results


@pytest.mark.asyncio
@patch("media.ocr.run_claude_print")
async def test_extract_image_text_returns_text(mock_run):
    mock_run.return_value = "這是圖片上的文字"
    result = await extract_image_text(Path("/tmp/test.jpg"))
    assert result == "這是圖片上的文字"


@pytest.mark.asyncio
@patch("media.ocr.run_claude_print")
async def test_extract_image_text_returns_empty_for_no_text(mock_run):
    mock_run.return_value = "無文字"
    result = await extract_image_text(Path("/tmp/test.jpg"))
    assert result == ""


def test_format_ocr_results_filters_empty():
    results = ["文字一", "", "文字二", ""]
    assert format_ocr_results(results) == "文字一\n\n文字二"


def test_format_ocr_results_returns_empty_for_all_empty():
    results = ["", "", ""]
    assert format_ocr_results(results) == ""
