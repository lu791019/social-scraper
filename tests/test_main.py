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
