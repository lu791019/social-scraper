import logging
from datetime import datetime, timezone

from notion_client import Client

from config import NOTION_TOKEN, NOTION_DATABASE_ID
from scraper.article import ArticleData

logger = logging.getLogger(__name__)

_RICH_TEXT_MAX = 2000  # Notion rich_text 單段上限
_BLOCK_BATCH_SIZE = 100  # Notion API 單次最多 100 blocks


def content_to_blocks(content: str) -> list[dict]:
    """將純文字內容轉為 Notion paragraph blocks"""
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    blocks = []
    for para in paragraphs:
        rich_text = _split_rich_text(para)
        blocks.append({"paragraph": {"rich_text": rich_text}})
    return blocks


def _split_rich_text(text: str) -> list[dict]:
    """將長文字切為 <=2000 字元的 rich_text 物件"""
    if len(text) <= _RICH_TEXT_MAX:
        return [{"type": "text", "text": {"content": text}}]
    chunks = []
    for i in range(0, len(text), _RICH_TEXT_MAX):
        chunks.append({"type": "text", "text": {"content": text[i : i + _RICH_TEXT_MAX]}})
    return chunks


def create_article_page(article: ArticleData) -> str:
    """在 Notion Database 建立文章頁面，回傳 page URL"""
    client = Client(auth=NOTION_TOKEN)

    properties = {
        "Title": {"title": [{"text": {"content": article.title}}]},
        "URL": {"url": article.url},
        "Source": {"select": {"name": article.source}},
        "Tags": {"multi_select": [{"name": t} for t in article.tags]},
        "Saved": {"date": {"start": datetime.now(timezone.utc).strftime("%Y-%m-%d")}},
    }
    if article.published_date:
        properties["Published"] = {"date": {"start": article.published_date}}

    page = client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties=properties,
    )

    # Append content blocks (max 100 per request)
    page_id = page["id"]
    blocks = content_to_blocks(article.content)
    for i in range(0, len(blocks), _BLOCK_BATCH_SIZE):
        batch = blocks[i : i + _BLOCK_BATCH_SIZE]
        client.blocks.children.append(block_id=page_id, children=batch)

    return page["url"]
