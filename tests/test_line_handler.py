from linebot.line_handler import extract_urls, is_supported_url


def test_extract_urls_instagram():
    text = "看看這個 https://www.instagram.com/p/abc123/ 很讚"
    urls = extract_urls(text)
    assert len(urls) == 1
    assert "instagram.com" in urls[0]


def test_extract_urls_threads():
    text = "https://www.threads.net/@user/post/abc123"
    urls = extract_urls(text)
    assert len(urls) == 1
    assert "threads.net" in urls[0]


def test_extract_urls_multiple():
    text = (
        "https://www.instagram.com/p/abc/ "
        "https://www.threads.net/@user/post/def"
    )
    urls = extract_urls(text)
    assert len(urls) == 2


def test_extract_urls_no_match():
    text = "今天天氣很好 https://twitter.com/post/123"
    urls = extract_urls(text)
    assert len(urls) == 0


def test_extract_urls_plain_text():
    text = "你好嗎"
    urls = extract_urls(text)
    assert len(urls) == 0


def test_is_supported_url_instagram():
    assert is_supported_url("https://www.instagram.com/p/abc123/")
    assert is_supported_url("https://instagram.com/reel/abc123/")


def test_is_supported_url_threads():
    assert is_supported_url("https://www.threads.net/@user/post/abc123")
    assert is_supported_url("https://threads.com/@user/post/abc123")


def test_is_supported_url_unsupported():
    assert not is_supported_url("https://twitter.com/post/123")
    assert not is_supported_url("https://youtube.com/watch?v=abc")
