import logging
import re
from datetime import datetime, timezone

from notion_client import Client

from config import NOTION_TOKEN, NOTION_DATABASE_ID
from scraper.article import ArticleData

logger = logging.getLogger(__name__)

_RICH_TEXT_MAX = 2000  # Notion rich_text 單段上限
_BLOCK_BATCH_SIZE = 100  # Notion API 單次最多 100 blocks

# Inline markdown: bold > italic > code > link（順序重要，**bold** 要先於 *italic*）
_INLINE_RE = re.compile(
    r"\*\*(.+?)\*\*"
    r"|\*(.+?)\*"
    r"|`(.+?)`"
    r"|\[([^\]]+)\]\(([^)]+)\)"
)


def _split_rich_text(text: str) -> list[dict]:
    """將長文字切為 <=2000 字元的 rich_text 物件"""
    if not text:
        return [{"type": "text", "text": {"content": ""}}]
    if len(text) <= _RICH_TEXT_MAX:
        return [{"type": "text", "text": {"content": text}}]
    chunks = []
    for i in range(0, len(text), _RICH_TEXT_MAX):
        chunks.append({"type": "text", "text": {"content": text[i : i + _RICH_TEXT_MAX]}})
    return chunks


def _parse_inline(text: str) -> list[dict]:
    """解析 inline markdown（bold/italic/code/link）為 Notion rich_text"""
    segments: list[dict] = []
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            segments.extend(_split_rich_text(text[pos : m.start()]))
        if m.group(1):  # **bold**
            segments.append({"type": "text", "text": {"content": m.group(1)}, "annotations": {"bold": True}})
        elif m.group(2):  # *italic*
            segments.append({"type": "text", "text": {"content": m.group(2)}, "annotations": {"italic": True}})
        elif m.group(3):  # `code`
            segments.append({"type": "text", "text": {"content": m.group(3)}, "annotations": {"code": True}})
        elif m.group(4):  # [text](url)
            url = m.group(5)
            if url.startswith(("http://", "https://")):
                segments.append({"type": "text", "text": {"content": m.group(4), "link": {"url": url}}})
            else:
                segments.append({"type": "text", "text": {"content": m.group(4)}})
        pos = m.end()
    if pos < len(text):
        segments.extend(_split_rich_text(text[pos:]))
    return segments or _split_rich_text(text)


def _is_block_start(line: str) -> bool:
    """判斷是否為 block 層級元素的起始行"""
    s = line.strip()
    if not s:
        return True
    if re.match(r"^#{1,3}\s", s):
        return True
    if re.match(r"^[\-\*\+]\s", s):
        # 排除水平線 ---
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            return True
        return True
    if re.match(r"^\d+\.\s", s):
        return True
    if s.startswith("> "):
        return True
    if s.startswith("```"):
        return True
    if re.match(r"^!\[.*\]\(.*\)$", s):
        return True
    return False


def content_to_blocks(content: str) -> list[dict]:
    """將 Markdown 內容轉為 Notion blocks（heading, list, quote, code, paragraph 等）"""
    lines = content.split("\n")
    blocks: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 空行跳過
        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append({"code": {"rich_text": _split_rich_text("\n".join(code_lines)), "language": lang}})
            if i < len(lines):
                i += 1  # skip closing ```
            continue

        # Heading
        hm = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if hm:
            level = len(hm.group(1))
            blocks.append({f"heading_{level}": {"rich_text": _parse_inline(hm.group(2).strip())}})
            i += 1
            continue

        # 水平線（在 list 判斷前，避免 --- 被誤判）
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            blocks.append({"divider": {}})
            i += 1
            continue

        # Bulleted list
        bm = re.match(r"^[\-\*\+]\s+(.*)", stripped)
        if bm:
            blocks.append({"bulleted_list_item": {"rich_text": _parse_inline(bm.group(1))}})
            i += 1
            continue

        # Numbered list
        nm = re.match(r"^\d+\.\s+(.*)", stripped)
        if nm:
            blocks.append({"numbered_list_item": {"rich_text": _parse_inline(nm.group(1))}})
            i += 1
            continue

        # Blockquote
        if stripped.startswith("> "):
            blocks.append({"quote": {"rich_text": _parse_inline(stripped[2:])}})
            i += 1
            continue

        # Image（只處理絕對 URL）
        img = re.match(r"^!\[(.*?)\]\((https?://.*?)\)$", stripped)
        if img:
            block: dict = {"image": {"type": "external", "external": {"url": img.group(2)}}}
            if img.group(1):
                block["image"]["caption"] = [{"type": "text", "text": {"content": img.group(1)}}]
            blocks.append(block)
            i += 1
            continue

        # Paragraph：收集連續非 block 行
        para_lines = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        text = " ".join(para_lines)
        blocks.append({"paragraph": {"rich_text": _parse_inline(text)}})

    return blocks


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
