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


def test_parse_ig_post_extracts_author():
    post = parse_ig_post({"caption": {"text": "hi"}, "user": {"username": "natgeo"}})
    assert post.author == "natgeo"


def test_parse_ig_post_falls_back_to_owner():
    post = parse_ig_post({"caption": {"text": "hi"}, "owner": {"username": "nasa"}})
    assert post.author == "nasa"


from scraper.instagram import ig_shortcode_from_url, find_post_by_code  # noqa: E402


def test_ig_shortcode_from_url():
    assert ig_shortcode_from_url("https://www.instagram.com/p/DAbc_1-x/") == "DAbc_1-x"
    assert ig_shortcode_from_url("https://www.instagram.com/reel/XyZ/?igsh=1") == "XyZ"
    assert ig_shortcode_from_url("https://www.instagram.com/natgeo/") is None


def test_find_ig_post_by_code_in_unknown_layout():
    data = {"x": [{"y": {"code": "XyZ", "user": {"username": "nasa"}, "caption": {"text": "hi"}}}]}
    assert parse_ig_post(find_post_by_code(data, "XyZ")).author == "nasa"
