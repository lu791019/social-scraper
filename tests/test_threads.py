import json
import pytest
from pathlib import Path
from scraper.threads import parse_threads_post, extract_post_from_threads_json
from scraper.instagram import PostData

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def threads_post_json():
    """Threads text post fixture"""
    with open(FIXTURES / "threads_post.json") as f:
        return json.load(f)


@pytest.fixture
def threads_wrapped_json():
    """Full page JSON structure wrapping a Threads post"""
    with open(FIXTURES / "threads_post_wrapped.json") as f:
        return json.load(f)


# --- BDD Scenario 1: 解析 Threads 文字貼文 ---
def test_parse_threads_post_extracts_caption(threads_post_json):
    result = parse_threads_post(threads_post_json)
    assert isinstance(result, PostData)
    assert len(result.caption) > 0
    assert "moon" in result.caption.lower()


def test_parse_threads_post_text_only_has_no_images(threads_post_json):
    """純文字 Threads 貼文沒有圖片（candidates 為空）"""
    result = parse_threads_post(threads_post_json)
    assert isinstance(result.image_urls, list)
    assert len(result.image_urls) == 0


def test_parse_threads_post_no_video(threads_post_json):
    result = parse_threads_post(threads_post_json)
    assert result.video_url is None


# --- BDD Scenario 2: 從完整頁面 JSON 提取 ---
def test_extract_post_from_threads_json(threads_wrapped_json):
    result = extract_post_from_threads_json(threads_wrapped_json)
    assert result is not None
    assert len(result.caption) > 0


# --- BDD Scenario 3: 解析失敗 ---
def test_extract_post_from_threads_json_empty():
    result = extract_post_from_threads_json({})
    assert result is None
