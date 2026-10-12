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


def test_parse_threads_post_extracts_author():
    post = parse_threads_post({"caption": {"text": "hi"}, "user": {"username": "zuck"}})
    assert post.author == "zuck"


def test_parse_threads_post_author_missing():
    assert parse_threads_post({"caption": {"text": "hi"}}).author == ""


# ── 2026 改版：目標貼文在 data.media，thread_items 是其他推薦串 ──

from scraper.threads import shortcode_from_url, find_post_by_code  # noqa: E402

_PAGE = {
    "require": [["x", "y", None, [{"__bbox": {"result": {"data": {"media": {
        "code": "TARGET1", "user": {"username": "zuck"},
        "caption": {"text": "本人貼文"},
        "image_versions2": {"candidates": [{"url": "https://img/t.jpg", "width": 10, "height": 10}]},
    }}}}}]]],
}
_OTHER = {"thread_items": [{"post": {"code": "OTHER", "user": {"username": "someone"}, "caption": {"text": "別人"}}}]}


def test_shortcode_from_url():
    assert shortcode_from_url("https://www.threads.com/@zuck/post/Dd1MqeVG3vT") == "Dd1MqeVG3vT"
    assert shortcode_from_url("https://www.threads.net/@a/post/AbC_-1/?xmt=1") == "AbC_-1"
    assert shortcode_from_url("https://www.threads.com/@zuck") is None


def test_find_post_by_code_picks_target_not_other_threads():
    assert find_post_by_code(_OTHER, "TARGET1") is None
    post = find_post_by_code(_PAGE, "TARGET1")
    assert post["user"]["username"] == "zuck"


def test_find_post_by_code_skips_stub_without_content():
    data = {"a": {"code": "X"}, "b": {"code": "X", "caption": {"text": "full"}}}
    assert find_post_by_code(data, "X")["caption"]["text"] == "full"


def test_parse_target_post_from_new_layout():
    post = parse_threads_post(find_post_by_code(_PAGE, "TARGET1"))
    assert post.author == "zuck"
    assert post.caption == "本人貼文"
    assert post.image_urls == ["https://img/t.jpg"]
