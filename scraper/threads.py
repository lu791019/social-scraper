import asyncio
import json
import random

from patchright.async_api import BrowserContext

from scraper.browser import human_like_scroll
from scraper.instagram import PostData, _extract_image, _extract_video
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
    post = PostData()

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


async def scrape_threads(context: BrowserContext, url: str) -> PostData:
    """用 Patchright 爬取 Threads 貼文頁面"""
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
        await asyncio.sleep(random.uniform(2, 5))
        await human_like_scroll(page)

        # 從 data-sjs script 提取
        scripts = await page.query_selector_all('script[type="application/json"]')
        for script in scripts:
            text = await script.inner_text()
            if "thread_items" not in text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
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
