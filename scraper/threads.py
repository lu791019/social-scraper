import asyncio
import random
import re

from patchright.async_api import BrowserContext

from scraper.browser import goto, human_like_scroll
from scraper.instagram import PostData, _extract_image, _extract_video, extract_author
from scraper.page_json import find_post_by_code, load_page_json  # noqa: F401 — 測試沿用 threads 路徑
from config import PAGE_TIMEOUT_MS


def parse_threads_post(item: dict) -> PostData:
    """從 Threads 貼文的 item dict 解析資料。

    Threads JSON 結構（2025+）：
    - caption: {text, pk, ...}
    - image_versions2: {candidates: [{url, width, height}, ...]}
    - video_versions: [{url, width, height}, ...] (影片才有)
    - carousel_media: [{image_versions2, video_versions, ...}, ...]
    - media_type: 19 (Threads 特有)
    """
    post = PostData(author=extract_author(item))

    # Caption
    caption = item.get("caption")
    if isinstance(caption, dict):
        post.caption = caption.get("text", "")
    elif isinstance(caption, str):
        post.caption = caption

    # 輪播
    carousel = item.get("carousel_media")
    if carousel and isinstance(carousel, list):
        for media in carousel:
            _extract_image(media, post)
            _extract_video(media, post)
    else:
        _extract_image(item, post)
        _extract_video(item, post)

    return post


def extract_post_from_threads_json(data: dict) -> PostData | None:
    """從完整頁面 JSON 中遞迴搜尋 thread_items 並提取貼文。"""
    items = _find_thread_items(data)
    if not items:
        return None
    post_data = items[0].get("post", items[0])
    return parse_threads_post(post_data)


def _find_thread_items(data, depth: int = 0) -> list | None:
    """遞迴搜尋 thread_items 陣列"""
    if depth > 20:
        return None
    if isinstance(data, dict):
        if "thread_items" in data:
            items = data["thread_items"]
            if isinstance(items, list) and items:
                return items
        for value in data.values():
            result = _find_thread_items(value, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                result = _find_thread_items(item, depth + 1)
                if result:
                    return result
    return None


_SHORTCODE_RE = re.compile(r"/post/([A-Za-z0-9_-]+)")


def shortcode_from_url(url: str) -> str | None:
    """https://www.threads.com/@user/post/<code> → <code>"""
    match = _SHORTCODE_RE.search(url)
    return match.group(1) if match else None


JSON_RETRY_ATTEMPTS = 4
JSON_RETRY_DELAY_S = 2.0


def _find_in_blobs(blobs: list, code: str) -> dict | None:
    for text, data in blobs:
        if code in text:
            item = find_post_by_code(data, code)
            if item:
                return item
    return None


async def scrape_threads(context: BrowserContext, url: str) -> PostData:
    """用 Patchright 爬取 Threads 貼文頁面"""
    page = await context.new_page()
    try:
        await goto(page, url, PAGE_TIMEOUT_MS)
        await asyncio.sleep(random.uniform(2, 5))
        await human_like_scroll(page)

        # 主要：用網址短碼精準比對目標貼文；JSON 偶爾晚於 networkidle 才出現，重讀幾次
        code = shortcode_from_url(url)
        blobs = await load_page_json(page)
        for attempt in range(JSON_RETRY_ATTEMPTS if code else 0):
            item = _find_in_blobs(blobs, code)
            if item:
                return parse_threads_post(item)
            if attempt < JSON_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(JSON_RETRY_DELAY_S)
                blobs = await load_page_json(page)

        # 舊版結構：thread_items（無短碼可比對時才用，可能是其他串）
        if not code:
            for text, data in blobs:
                if "thread_items" not in text:
                    continue
                post = extract_post_from_threads_json(data)
                if post and (post.caption or post.image_urls or post.video_url):
                    return post

        # 備用：從 meta tag 取 caption
        meta = await page.query_selector('meta[property="og:description"]')
        if meta:
            content = await meta.get_attribute("content")
            if content:
                return PostData(caption=content)

        raise RuntimeError("Threads 解析失敗：找不到貼文資料")
    finally:
        await page.close()
