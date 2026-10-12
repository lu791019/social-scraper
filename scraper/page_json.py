"""頁面內嵌 JSON 的共用工具（IG / Threads 共用）"""
import json

_CONTENT_KEYS = ("caption", "image_versions2", "video_versions", "carousel_media")


def find_post_by_code(data, code: str, depth: int = 0) -> dict | None:
    """遞迴找 code == 網址短碼、且帶內容欄位的貼文 dict。

    2026 改版後目標貼文在 __bbox.result.data.media；thread_items 變成頁面上的其他推薦串，
    直接取 thread_items[0] 會抓到別人的貼文。
    """
    if depth > 40:
        return None
    if isinstance(data, dict):
        if data.get("code") == code and any(data.get(k) for k in _CONTENT_KEYS):
            return data
        children = data.values()
    elif isinstance(data, list):
        children = data
    else:
        return None
    for child in children:
        if isinstance(child, (dict, list)):
            found = find_post_by_code(child, code, depth + 1)
            if found:
                return found
    return None


async def load_page_json(page) -> list:
    """取出頁面上所有可解析的 application/json script"""
    blobs = []
    for script in await page.query_selector_all('script[type="application/json"]'):
        text = await script.inner_text()
        try:
            blobs.append((text, json.loads(text)))
        except json.JSONDecodeError:
            continue
    return blobs

