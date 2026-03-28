from scraper.article import clean_url, extract_metadata, extract_content


def test_clean_url_removes_utm_params():
    dirty = "https://www.bnext.com.tw/article/123?utm_source=line&utm_medium=message&openExternalBrowser=1"
    assert clean_url(dirty) == "https://www.bnext.com.tw/article/123"


def test_clean_url_preserves_meaningful_params():
    url = "https://example.com/search?q=python&page=2"
    assert clean_url(url) == "https://example.com/search?q=python&page=2"


def test_clean_url_removes_mixed_tracking():
    dirty = "https://example.com/post?id=5&utm_campaign=spring&ldtag_cl=abc&lt_r=134"
    assert clean_url(dirty) == "https://example.com/post?id=5"


def test_clean_url_no_params():
    url = "https://example.com/article/hello"
    assert clean_url(url) == "https://example.com/article/hello"


SAMPLE_HTML = """
<html><head>
<meta property="og:title" content="Test Article Title">
<meta property="og:description" content="This is a test description">
<meta property="article:published_time" content="2026-03-20T11:30:00+08:00">
<meta property="article:tag" content="AI">
<meta property="article:tag" content="Tech">
<title>Test Article Title | SiteName</title>
</head><body><article><p>Article content here</p></article></body></html>
"""

SAMPLE_JSONLD_HTML = """
<html><head>
<title>JSON-LD Article</title>
<script type="application/ld+json">
{"@type": "NewsArticle", "headline": "JSON-LD Title", "datePublished": "2026-01-15T09:00:00Z", "description": "LD description"}
</script>
</head><body><p>Content</p></body></html>
"""

MINIMAL_HTML = """
<html><head><title>Just a Title</title></head><body><p>Hello</p></body></html>
"""


def test_extract_metadata_og_tags():
    meta = extract_metadata(SAMPLE_HTML)
    assert meta["title"] == "Test Article Title"
    assert meta["description"] == "This is a test description"
    assert meta["published_date"] == "2026-03-20"
    assert meta["tags"] == ["AI", "Tech"]


def test_extract_metadata_jsonld():
    meta = extract_metadata(SAMPLE_JSONLD_HTML)
    assert meta["title"] == "JSON-LD Title"
    assert meta["published_date"] == "2026-01-15"
    assert meta["description"] == "LD description"


def test_extract_metadata_minimal():
    meta = extract_metadata(MINIMAL_HTML)
    assert meta["title"] == "Just a Title"
    assert meta["description"] is None
    assert meta["published_date"] is None
    assert meta["tags"] == []


def test_parse_date_short_string():
    from scraper.article import _parse_date
    assert _parse_date("2026-03-20T11:30:00") == "2026-03-20"
    assert _parse_date("2026-03") is None
    assert _parse_date("invalid") is None


ARTICLE_HTML = """
<html><head><title>Test</title></head>
<body>
<nav>Navigation bar</nav>
<article>
<p>First paragraph of the article.</p>
<p>Second paragraph with important info.</p>
</article>
<footer>Footer stuff</footer>
</body></html>
"""


def test_extract_content_strips_nav_footer():
    content = extract_content(ARTICLE_HTML)
    assert "First paragraph" in content
    assert "Second paragraph" in content
    assert len(content) > 10


def test_extract_content_returns_plain_text():
    content = extract_content(ARTICLE_HTML)
    assert "<p>" not in content
    assert "<article>" not in content


FULL_HTML = """
<html><head>
<meta property="og:title" content="Great Article">
<meta property="og:description" content="A summary">
<meta property="article:published_time" content="2026-03-20T11:30:00+08:00">
</head><body>
<article><p>This is the main article content.</p><p>Another paragraph.</p></article>
</body></html>
"""


import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_scrape_article_returns_article_data():
    from scraper.article import scrape_article, ArticleData

    mock_response = AsyncMock()
    mock_response.text = FULL_HTML
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    with patch("scraper.article.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        article = await scrape_article("https://example.com/article?utm_source=test")

    assert isinstance(article, ArticleData)
    assert article.title == "Great Article"
    assert article.url == "https://example.com/article"
    assert article.source == "example.com"
    assert article.published_date == "2026-03-20"
    assert "main article content" in article.content
