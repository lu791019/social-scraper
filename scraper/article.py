from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field
from html import unescape
from typing import Optional
from urllib.parse import urlparse, urlencode, parse_qs

logger = logging.getLogger(__name__)

# 要移除的 tracking query params
_TRACKING_PARAMS = re.compile(
    r"^(utm_|openExternalBrowser|ldtag_cl|lt_r|srclt|_ly_)"
)


@dataclass
class ArticleData:
    title: str
    url: str
    source: str
    published_date: str | None = None
    tags: list[str] = field(default_factory=list)
    description: str | None = None
    content: str = ""


def clean_url(url: str) -> str:
    """移除 URL 中的 tracking parameters"""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in params.items() if not _TRACKING_PARAMS.match(k)}
    if cleaned:
        query = urlencode(cleaned, doseq=True)
        return parsed._replace(query=query, fragment="").geturl()
    return parsed._replace(query="", fragment="").geturl()


def extract_metadata(html: str) -> dict:
    """從 HTML 的 meta tags 和 JSON-LD 提取 metadata"""
    result = {"title": None, "description": None, "published_date": None, "tags": []}

    # 1. OG / article meta tags
    og_title = _find_meta(html, "og:title")
    og_desc = _find_meta(html, "og:description")
    pub_date = (
        _find_meta(html, "article:published_time")
        or _find_meta(html, "my:publish_date")
    )
    tags = _find_all_meta(html, "article:tag") or _find_all_meta(html, "my:tags")

    # 2. JSON-LD fallback
    ld_match = re.search(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    ld_data = {}
    if ld_match:
        try:
            ld_data = json.loads(ld_match.group(1))
            if isinstance(ld_data, list):
                ld_data = ld_data[0] if ld_data else {}
        except (json.JSONDecodeError, IndexError):
            pass

    # 3. <title> fallback
    title_match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    fallback_title = unescape(title_match.group(1)).strip() if title_match else ""

    # Merge: OG > JSON-LD > <title>
    result["title"] = og_title or ld_data.get("headline") or fallback_title or "Untitled"
    result["description"] = og_desc or ld_data.get("description")
    raw_date = pub_date or ld_data.get("datePublished")
    result["published_date"] = _parse_date(raw_date) if raw_date else None
    result["tags"] = tags

    return result


def _find_meta(html: str, prop: str) -> str | None:
    pattern = rf'<meta\s+(?:property|name)="{re.escape(prop)}"\s+content="(.*?)"'
    m = re.search(pattern, html)
    if m:
        return unescape(m.group(1))
    # content-first variant
    pattern2 = rf'<meta\s+content="(.*?)"\s+(?:property|name)="{re.escape(prop)}"'
    m2 = re.search(pattern2, html)
    return unescape(m2.group(1)) if m2 else None


def _find_all_meta(html: str, prop: str) -> list[str]:
    pattern = rf'<meta\s+(?:property|name)="{re.escape(prop)}"\s+content="(.*?)"'
    results = [unescape(m) for m in re.findall(pattern, html)]
    if not results:
        pattern2 = rf'<meta\s+content="(.*?)"\s+(?:property|name)="{re.escape(prop)}"'
        results = [unescape(m) for m in re.findall(pattern2, html)]
    return results


def _parse_date(raw: str) -> str | None:
    """從各種日期格式提取 YYYY-MM-DD，無法解析時回傳 None"""
    m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
    return m.group(1) if m else None
