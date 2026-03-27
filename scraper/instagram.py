import asyncio
import json
import random
from dataclasses import dataclass, field

from patchright.async_api import BrowserContext

from scraper.browser import human_like_scroll
from config import PAGE_TIMEOUT_MS


@dataclass
class PostData:
    caption: str = ""
    image_urls: list[str] = field(default_factory=list)
    video_url: str | None = None


def parse_ig_post(item: dict) -> PostData:
    """從 IG 單篇貼文的 item dict 解析資料。

    IG 新版 JSON 結構（2025+）：
    - caption: {text, pk, ...}
    - image_versions2: {candidates: [{url, width, height}, ...]}
    - video_versions: [{url, width, height, type}, ...] (影片/Reels 才有)
    - carousel_media: [{image_versions2, video_versions, ...}, ...] (輪播才有)
    - media_type: 1=photo, 2=video, 8=carousel
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
        # 單張圖片
        _extract_image(item, post)
        # 影片
        _extract_video(item, post)

    return post


def _extract_image(item: dict, post: PostData) -> None:
    """從 item 的 image_versions2 取得最高解析度圖片 URL"""
    candidates = item.get("image_versions2", {}).get("candidates", [])
    if candidates:
        best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
        url = best.get("url", "")
        if url:
            post.image_urls.append(url)


def _extract_video(item: dict, post: PostData) -> None:
    """從 item 的 video_versions 取得最高解析度影片 URL"""
    if post.video_url:
        return
    video_versions = item.get("video_versions")
    if video_versions and isinstance(video_versions, list):
        best = max(video_versions, key=lambda v: v.get("width", 0) * v.get("height", 0))
        url = best.get("url", "")
        if url:
            post.video_url = url


def extract_post_from_json(data: dict) -> PostData | None:
    """從完整頁面 JSON 中遞迴搜尋並提取貼文資料。

    搜尋目標 key：xdt_api__v1__media__shortcode__web_info
    路徑範例：require[0][3][0].__bbox.require[0][3][1].__bbox.result.data.xdt_api__v1__media__shortcode__web_info.items[0]
    """
    items = _find_shortcode_items(data)
    if items:
        return parse_ig_post(items[0])
    return None


def _find_shortcode_items(data, depth: int = 0) -> list | None:
    """遞迴搜尋 xdt_api__v1__media__shortcode__web_info.items"""
    if depth > 15:
        return None
    if isinstance(data, dict):
        if "xdt_api__v1__media__shortcode__web_info" in data:
            info = data["xdt_api__v1__media__shortcode__web_info"]
            if isinstance(info, dict) and "items" in info:
                return info["items"]
        for value in data.values():
            result = _find_shortcode_items(value, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_shortcode_items(item, depth + 1)
            if result:
                return result
    return None


async def scrape_instagram(context: BrowserContext, url: str) -> PostData:
    """用 Patchright 爬取 IG 貼文頁面"""
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=PAGE_TIMEOUT_MS)
        await asyncio.sleep(random.uniform(2, 5))
        await human_like_scroll(page)

        # 檢查登入牆
        login_form = await page.query_selector('input[name="username"]')
        if login_form:
            raise RuntimeError("需要登入，無法匿名存取此貼文")

        # 從嵌入 JSON 提取資料
        scripts = await page.query_selector_all('script[type="application/json"]')
        for script in scripts:
            text = await script.inner_text()
            if "xdt_api__v1__media__shortcode" not in text:
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            post = extract_post_from_json(data)
            if post and (post.caption or post.image_urls or post.video_url):
                return post

        # 備用：從 meta tag 取 caption
        meta = await page.query_selector('meta[property="og:description"]')
        if meta:
            content = await meta.get_attribute("content")
            if content:
                return PostData(caption=content)

        raise RuntimeError("IG 解析失敗：找不到貼文資料")
    finally:
        await page.close()
