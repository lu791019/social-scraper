import json
import pytest
from pathlib import Path
from scraper.instagram import parse_ig_post, extract_post_from_json, PostData

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ig_photo_json():
    """Photo post fixture (media_type=1)"""
    with open(FIXTURES / "ig_post.json") as f:
        return json.load(f)


@pytest.fixture
def ig_reel_json():
    """Reel fixture (media_type=2, has video_versions)"""
    with open(FIXTURES / "ig_reel.json") as f:
        return json.load(f)


@pytest.fixture
def ig_wrapped_json():
    """Full page JSON structure wrapping a post"""
    with open(FIXTURES / "ig_post_wrapped.json") as f:
        return json.load(f)


def test_parse_ig_post_extracts_caption(ig_photo_json):
    result = parse_ig_post(ig_photo_json)
    assert isinstance(result, PostData)
    assert len(result.caption) > 0
    assert "procrastination" in result.caption.lower()


def test_parse_ig_post_extracts_image_urls(ig_photo_json):
    result = parse_ig_post(ig_photo_json)
    assert isinstance(result.image_urls, list)
    assert len(result.image_urls) >= 1
    for url in result.image_urls:
        assert url.startswith("http")


def test_parse_ig_post_photo_has_no_video(ig_photo_json):
    result = parse_ig_post(ig_photo_json)
    assert result.video_url is None


def test_parse_ig_reel_extracts_video_url(ig_reel_json):
    result = parse_ig_post(ig_reel_json)
    assert result.video_url is not None
    assert result.video_url.startswith("http")


def test_parse_ig_reel_extracts_caption(ig_reel_json):
    result = parse_ig_post(ig_reel_json)
    assert len(result.caption) > 0


def test_extract_post_from_json_unwraps_structure(ig_wrapped_json):
    """從完整頁面 JSON 中提取貼文資料"""
    result = extract_post_from_json(ig_wrapped_json)
    assert result is not None
    assert len(result.caption) > 0
    assert len(result.image_urls) >= 1
