from services.notion import content_to_blocks


def test_content_to_blocks_splits_paragraphs():
    content = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    blocks = content_to_blocks(content)
    assert len(blocks) == 3
    assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "First paragraph."
    assert blocks[2]["paragraph"]["rich_text"][0]["text"]["content"] == "Third paragraph."


def test_content_to_blocks_skips_empty():
    content = "First.\n\n\n\nSecond."
    blocks = content_to_blocks(content)
    assert len(blocks) == 2


def test_content_to_blocks_truncates_long_text():
    # Notion rich_text max 2000 chars per text object
    long_para = "A" * 2500
    blocks = content_to_blocks(long_para)
    # Should split into multiple rich_text objects within one paragraph
    texts = blocks[0]["paragraph"]["rich_text"]
    assert all(len(t["text"]["content"]) <= 2000 for t in texts)
    total = sum(len(t["text"]["content"]) for t in texts)
    assert total == 2500


def test_content_to_blocks_many_paragraphs():
    # Over 100 paragraphs — returns flat list, batching is in create_article_page
    content = "\n\n".join(f"Paragraph {i}" for i in range(150))
    blocks = content_to_blocks(content)
    assert len(blocks) == 150


import pytest
from unittest.mock import patch, MagicMock
from scraper.article import ArticleData


@pytest.fixture
def sample_article():
    return ArticleData(
        title="Test Article",
        url="https://example.com/test",
        source="example.com",
        published_date="2026-03-20",
        tags=["AI", "Tech"],
        description="A test article",
        content="First paragraph.\n\nSecond paragraph.",
    )


@pytest.fixture
def mock_notion():
    with patch("services.notion.Client") as mock_cls:
        client = MagicMock()
        mock_cls.return_value = client
        client.pages.create.return_value = {
            "id": "page-id-123",
            "url": "https://www.notion.so/Test-Article-abc123",
        }
        client.blocks.children.append.return_value = {"results": []}
        yield client


def test_create_article_page_returns_url(sample_article, mock_notion):
    from services.notion import create_article_page
    url = create_article_page(sample_article)
    assert url == "https://www.notion.so/Test-Article-abc123"


def test_create_article_page_sets_properties(sample_article, mock_notion):
    from services.notion import create_article_page
    create_article_page(sample_article)
    call_kwargs = mock_notion.pages.create.call_args
    props = call_kwargs.kwargs["properties"]
    assert props["Title"]["title"][0]["text"]["content"] == "Test Article"
    assert props["URL"]["url"] == "https://example.com/test"
    assert props["Source"]["select"]["name"] == "example.com"
    assert props["Published"]["date"]["start"] == "2026-03-20"
    assert len(props["Tags"]["multi_select"]) == 2
    assert props["Tags"]["multi_select"][0]["name"] == "AI"


def test_create_article_page_appends_content(sample_article, mock_notion):
    from services.notion import create_article_page
    create_article_page(sample_article)
    mock_notion.blocks.children.append.assert_called_once()
    call_kwargs = mock_notion.blocks.children.append.call_args
    children = call_kwargs.kwargs["children"]
    assert len(children) == 2  # 2 paragraphs


def test_create_article_page_no_optional_fields(mock_notion):
    from services.notion import create_article_page
    article = ArticleData(
        title="Minimal",
        url="https://example.com",
        source="example.com",
        content="Some content.",
    )
    create_article_page(article)
    props = mock_notion.pages.create.call_args.kwargs["properties"]
    assert "Published" not in props
    assert props["Tags"]["multi_select"] == []
