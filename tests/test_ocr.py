import pytest
from pathlib import Path
from unittest.mock import patch
from media.ocr import extract_image_text, extract_images_text_batch, format_ocr_results


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


@pytest.mark.asyncio
@patch("media.ocr.run_claude_print")
async def test_extract_images_text_batch_single_image(mock_run):
    """單張圖走 extract_image_text 路徑"""
    mock_run.return_value = "單張圖片文字"
    result = await extract_images_text_batch([Path("/tmp/test.jpg")])
    assert result == "單張圖片文字"


@pytest.mark.asyncio
@patch("media.ocr.run_claude_print")
async def test_extract_images_text_batch_multiple(mock_run):
    """多張圖走批次路徑"""
    mock_run.return_value = "---圖片1---\n第一張文字\n---圖片2---\n無文字\n---圖片3---\n第三張文字"
    result = await extract_images_text_batch([
        Path("/tmp/1.jpg"), Path("/tmp/2.jpg"), Path("/tmp/3.jpg"),
    ])
    assert "第一張文字" in result
    assert "第三張文字" in result
    assert "無文字" not in result
    mock_run.assert_called_once()


def test_format_ocr_results_filters_empty():
    results = ["文字一", "", "文字二", ""]
    assert format_ocr_results(results) == "文字一\n\n文字二"


def test_format_ocr_results_returns_empty_for_all_empty():
    results = ["", "", ""]
    assert format_ocr_results(results) == ""
