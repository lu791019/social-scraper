# Social Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 從 Google Sheet 讀取 IG/Threads URL，用 Patchright 爬取內容（文字 + 圖片 OCR + 影片逐字稿），Claude API 產摘要，寫回 Sheet。

**Architecture:** Patchright 無頭瀏覽器開貼文頁面，從嵌入 JSON 提取結構化資料（caption、圖片 URL、影片 URL）。圖片用 Claude Vision OCR，影片用 ffmpeg + Whisper 轉逐字稿。全部文字彙整後由 Claude Sonnet 產出摘要，透過 gspread 寫回 Google Sheet。

**Tech Stack:** Python 3.12+, Patchright (async), gspread, anthropic SDK, openai SDK (Whisper), ffmpeg, httpx, uv

**Design Doc:** `docs/plans/2026-02-19-social-scraper-design.md`

---

### Task 1: 專案骨架與依賴

**Files:**
- Create: `pyproject.toml`
- Create: `config.py`
- Create: `.env.example`
- Modify: `.gitignore`

**Step 1: 初始化 uv 專案並安裝依賴**

```bash
cd /Users/dex/social-scraper
uv init --python 3.12
```

編輯 `pyproject.toml`：

```toml
[project]
name = "social-scraper"
version = "0.1.0"
description = "IG/Threads 爬蟲 + LLM 摘要工具"
requires-python = ">=3.12"
dependencies = [
    "patchright>=1.58",
    "gspread>=6.0",
    "anthropic>=0.40",
    "openai>=1.50",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]
```

```bash
uv sync
```

**Step 2: 建立 config.py**

```python
# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# API Keys
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Google Sheet
GOOGLE_SHEET_URL = os.environ["GOOGLE_SHEET_URL"]
GOOGLE_CREDENTIALS_PATH = Path(os.environ.get(
    "GOOGLE_CREDENTIALS_PATH", "credentials.json"
))

# Scraper settings
DAILY_LIMIT = 30
REQUEST_DELAY_MIN = 3.0
REQUEST_DELAY_MAX = 8.0
PAGE_TIMEOUT_MS = 30_000
MAX_RETRIES = 1

# Proxy (None for MVP)
PROXY_URL: str | None = os.environ.get("PROXY_URL")

# Temp directory for video downloads
TEMP_DIR = Path("/tmp/social-scraper")
```

**Step 3: 建立 .env.example**

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/xxx/edit
GOOGLE_CREDENTIALS_PATH=credentials.json
# PROXY_URL=http://user:pass@proxy:port
```

**Step 4: 更新 .gitignore 並建立套件目錄**

在 `.gitignore` 追加：

```
# Credentials
credentials.json

# Temp
/tmp/
```

建立套件目錄：

```bash
mkdir -p scraper media services tests
touch scraper/__init__.py media/__init__.py services/__init__.py tests/__init__.py
```

**Step 5: Commit**

```bash
git add pyproject.toml config.py .env.example .gitignore scraper/ media/ services/ tests/
git commit -m "feat: 專案骨架、依賴設定與目錄結構"
```

---

### Task 2: 瀏覽器管理模組（Patchright + 防封）

**Files:**
- Create: `scraper/browser.py`
- Create: `tests/test_browser.py`

**Step 1: 寫 browser.py 的測試**

```python
# tests/test_browser.py
import pytest
from scraper.browser import random_ua, random_viewport, VIEWPORTS, USER_AGENTS


def test_random_ua_returns_string_from_pool():
    ua = random_ua()
    assert ua in USER_AGENTS
    assert "Mozilla" in ua


def test_random_viewport_returns_valid_dict():
    vp = random_viewport()
    assert "width" in vp and "height" in vp
    assert vp in VIEWPORTS


def test_ua_pool_has_multiple_entries():
    assert len(USER_AGENTS) >= 5


def test_viewport_pool_has_multiple_entries():
    assert len(VIEWPORTS) >= 3
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_browser.py -v
```

預期：FAIL — `ModuleNotFoundError: No module named 'scraper.browser'`

**Step 3: 實作 browser.py**

```python
# scraper/browser.py
import random
from patchright.async_api import async_playwright, Browser, BrowserContext, Page

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
]

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1920, "height": 1080},
    {"width": 1280, "height": 720},
]


def random_ua() -> str:
    return random.choice(USER_AGENTS)


def random_viewport() -> dict[str, int]:
    return random.choice(VIEWPORTS)


async def human_like_scroll(page: Page) -> None:
    """模擬人類滾動行為"""
    import asyncio

    scroll_count = random.randint(1, 3)
    for _ in range(scroll_count):
        distance = random.randint(300, 800)
        await page.mouse.wheel(0, distance)
        await asyncio.sleep(random.uniform(0.5, 1.5))


async def create_browser(proxy: str | None = None) -> tuple[Browser, BrowserContext]:
    """建立 Patchright 瀏覽器與 context，套用防封設定"""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        proxy={"server": proxy} if proxy else None,
    )
    context = await browser.new_context(
        viewport=random_viewport(),
        user_agent=random_ua(),
        locale="zh-TW",
        timezone_id="Asia/Taipei",
    )
    return browser, context
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_browser.py -v
```

預期：全部 PASS

**Step 5: Commit**

```bash
git add scraper/browser.py tests/test_browser.py
git commit -m "feat: 瀏覽器管理模組，含 UA/viewport 輪替與人類滾動模擬"
```

---

### Task 3: Instagram 爬蟲模組

**Files:**
- Create: `scraper/instagram.py`
- Create: `tests/test_instagram.py`
- Create: `tests/fixtures/ig_post.html` (spike 取得)

**Step 1: Spike — 擷取真實 IG 頁面的嵌入 JSON 結構**

> 這是探索步驟。用 Patchright 開一個公開 IG 貼文頁面，印出所有 `<script type="application/json">` 的內容，找出包含 caption、圖片 URL、影片 URL 的 JSON 路徑。

```python
# spike_ig.py（臨時腳本，用完刪除）
import asyncio
import json
from patchright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    page = await browser.new_page()

    # 用一個公開 IG 貼文 URL 測試
    await page.goto("https://www.instagram.com/p/EXAMPLE_POST_ID/", wait_until="networkidle")

    scripts = await page.query_selector_all('script[type="application/json"]')
    for i, script in enumerate(scripts):
        text = await script.inner_text()
        data = json.loads(text)
        # 存成檔案方便分析
        with open(f"tests/fixtures/ig_script_{i}.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Script {i}: {len(text)} chars, keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")

    await browser.close()
    await pw.stop()


asyncio.run(main())
```

```bash
uv run python spike_ig.py
```

分析輸出的 JSON 檔案，找到包含以下欄位的路徑：
- `caption`（貼文文字）
- `display_url` 或 `image_versions2`（圖片）
- `video_url`（影片，Reels 才有）

將包含貼文資料的 JSON 精簡後存為 `tests/fixtures/ig_post.json`。

**Step 2: 根據 spike 結果寫測試 fixture 和測試**

```python
# tests/test_instagram.py
import json
import pytest
from pathlib import Path
from scraper.instagram import parse_ig_post, PostData

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def ig_post_json():
    """從 spike 取得的真實 JSON 結構"""
    with open(FIXTURES / "ig_post.json") as f:
        return json.load(f)


def test_parse_ig_post_extracts_caption(ig_post_json):
    result = parse_ig_post(ig_post_json)
    assert isinstance(result, PostData)
    assert len(result.caption) > 0


def test_parse_ig_post_extracts_image_urls(ig_post_json):
    result = parse_ig_post(ig_post_json)
    assert isinstance(result.image_urls, list)
    for url in result.image_urls:
        assert url.startswith("http")


def test_parse_ig_post_video_url_is_none_for_photo(ig_post_json):
    """照片貼文沒有 video_url"""
    result = parse_ig_post(ig_post_json)
    # video_url 可能是 None（照片）或字串（影片/Reels）
    assert result.video_url is None or result.video_url.startswith("http")
```

**Step 3: 跑測試確認失敗**

```bash
uv run pytest tests/test_instagram.py -v
```

預期：FAIL

**Step 4: 實作 instagram.py**

> 注意：`parse_ig_post` 的實際 JSON 路徑需要根據 Step 1 的 spike 結果調整。以下是基於已知 IG 結構的範本。

```python
# scraper/instagram.py
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


def parse_ig_post(data: dict) -> PostData:
    """從 IG 嵌入 JSON 解析貼文資料。

    JSON 結構路徑需根據 spike 結果調整。
    常見路徑：
    - data.xdt_shortcode_media.edge_media_to_caption.edges[0].node.text
    - data.xdt_shortcode_media.display_url
    - data.xdt_shortcode_media.video_url
    - data.xdt_shortcode_media.edge_sidecar_to_children.edges (輪播)
    """
    post = PostData()

    # 遍歷找到包含 shortcode_media 的節點
    media = _find_media(data)
    if not media:
        return post

    # Caption
    caption_edges = (
        media.get("edge_media_to_caption", {}).get("edges", [])
    )
    if caption_edges:
        post.caption = caption_edges[0].get("node", {}).get("text", "")

    # 圖片
    if "edge_sidecar_to_children" in media:
        # 輪播貼文
        for edge in media["edge_sidecar_to_children"].get("edges", []):
            node = edge.get("node", {})
            url = node.get("display_url", "")
            if url:
                post.image_urls.append(url)
    else:
        url = media.get("display_url", "")
        if url:
            post.image_urls.append(url)

    # 影片
    if media.get("is_video"):
        post.video_url = media.get("video_url")

    return post


def _find_media(data: dict, depth: int = 0) -> dict | None:
    """遞迴搜尋包含 shortcode_media 或 display_url 的節點"""
    if depth > 10:
        return None
    if not isinstance(data, dict):
        return None

    # 直接找到目標
    for key in ("xdt_shortcode_media", "shortcode_media"):
        if key in data:
            return data[key]

    # 如果當前節點看起來像 media 節點
    if "display_url" in data and "edge_media_to_caption" in data:
        return data

    # 遞迴搜尋
    for value in data.values():
        if isinstance(value, dict):
            result = _find_media(value, depth + 1)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _find_media(item, depth + 1)
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
            raise RuntimeError("需要登入")

        # 從嵌入 JSON 提取資料
        scripts = await page.query_selector_all('script[type="application/json"]')
        for script in scripts:
            text = await script.inner_text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            post = parse_ig_post(data)
            if post.caption or post.image_urls or post.video_url:
                return post

        # 備用：從 meta tag 取 caption
        meta = await page.query_selector('meta[property="og:description"]')
        if meta:
            content = await meta.get_attribute("content")
            if content:
                return PostData(caption=content)

        raise RuntimeError("解析失敗")
    finally:
        await page.close()
```

**Step 5: 跑測試確認通過**

```bash
uv run pytest tests/test_instagram.py -v
```

預期：全部 PASS（需要 fixture 檔案）

**Step 6: Commit**

```bash
git add scraper/instagram.py tests/test_instagram.py tests/fixtures/
git commit -m "feat: Instagram 爬蟲模組，含 JSON 解析與登入牆偵測"
```

---

### Task 4: Threads 爬蟲模組

**Files:**
- Create: `scraper/threads.py`
- Create: `tests/test_threads.py`

**Step 1: Spike — 擷取真實 Threads 頁面結構**

```python
# spike_threads.py（臨時腳本，用完刪除）
import asyncio
import json
from patchright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    page = await browser.new_page()

    await page.goto("https://www.threads.net/@EXAMPLE_USER/post/EXAMPLE_ID", wait_until="networkidle")

    scripts = await page.query_selector_all('script[type="application/json"][data-sjs]')
    for i, script in enumerate(scripts):
        text = await script.inner_text()
        data = json.loads(text)
        with open(f"tests/fixtures/threads_script_{i}.json", "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Script {i}: {len(text)} chars")

    await browser.close()
    await pw.stop()


asyncio.run(main())
```

```bash
uv run python spike_threads.py
```

分析 JSON 結構，找到 caption、圖片、影片欄位路徑，精簡後存為 `tests/fixtures/threads_post.json`。

**Step 2: 寫測試**

```python
# tests/test_threads.py
import json
import pytest
from pathlib import Path
from scraper.threads import parse_threads_post
from scraper.instagram import PostData  # 共用 PostData

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def threads_post_json():
    with open(FIXTURES / "threads_post.json") as f:
        return json.load(f)


def test_parse_threads_post_extracts_caption(threads_post_json):
    result = parse_threads_post(threads_post_json)
    assert isinstance(result, PostData)
    assert len(result.caption) > 0


def test_parse_threads_post_extracts_image_urls(threads_post_json):
    result = parse_threads_post(threads_post_json)
    assert isinstance(result.image_urls, list)
```

**Step 3: 跑測試確認失敗**

```bash
uv run pytest tests/test_threads.py -v
```

**Step 4: 實作 threads.py**

> JSON 路徑需根據 spike 結果調整。Threads 的嵌入 JSON 通常在 `require` 陣列中，使用 `nested_lookup` 風格搜尋。

```python
# scraper/threads.py
import asyncio
import json
import random

from patchright.async_api import BrowserContext

from scraper.browser import human_like_scroll
from scraper.instagram import PostData
from config import PAGE_TIMEOUT_MS


def parse_threads_post(data: dict) -> PostData:
    """從 Threads 嵌入 JSON 解析貼文資料。

    Threads JSON 結構較深，常見路徑：
    - require[...].result.data.containing_thread.thread_items[0].post.caption.text
    - require[...].result.data.containing_thread.thread_items[0].post.image_versions2
    - require[...].result.data.containing_thread.thread_items[0].post.video_versions
    """
    post = PostData()

    # 搜尋 thread_items
    thread_items = _find_thread_items(data)
    if not thread_items:
        return post

    first_post = thread_items[0] if thread_items else {}
    post_data = first_post.get("post", {})

    # Caption
    caption_obj = post_data.get("caption")
    if isinstance(caption_obj, dict):
        post.caption = caption_obj.get("text", "")
    elif isinstance(caption_obj, str):
        post.caption = caption_obj

    # 圖片
    image_versions = post_data.get("image_versions2", {})
    candidates = image_versions.get("candidates", [])
    if candidates:
        # 取最高解析度
        best = max(candidates, key=lambda c: c.get("width", 0) * c.get("height", 0))
        url = best.get("url", "")
        if url:
            post.image_urls.append(url)

    # 輪播
    carousel = post_data.get("carousel_media", [])
    for item in carousel:
        img = item.get("image_versions2", {}).get("candidates", [])
        if img:
            best = max(img, key=lambda c: c.get("width", 0) * c.get("height", 0))
            url = best.get("url", "")
            if url:
                post.image_urls.append(url)

    # 影片
    video_versions = post_data.get("video_versions", [])
    if video_versions:
        best = max(video_versions, key=lambda v: v.get("width", 0) * v.get("height", 0))
        post.video_url = best.get("url")

    return post


def _find_thread_items(data, depth: int = 0) -> list | None:
    """遞迴搜尋 thread_items 陣列"""
    if depth > 15:
        return None
    if isinstance(data, dict):
        if "thread_items" in data:
            return data["thread_items"]
        for value in data.values():
            result = _find_thread_items(value, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
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
        scripts = await page.query_selector_all('script[type="application/json"][data-sjs]')
        for script in scripts:
            text = await script.inner_text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            post = parse_threads_post(data)
            if post.caption or post.image_urls or post.video_url:
                return post

        # 備用：一般 script 標籤
        scripts = await page.query_selector_all('script[type="application/json"]')
        for script in scripts:
            text = await script.inner_text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            post = parse_threads_post(data)
            if post.caption or post.image_urls or post.video_url:
                return post

        raise RuntimeError("解析失敗")
    finally:
        await page.close()
```

**Step 5: 跑測試確認通過**

```bash
uv run pytest tests/test_threads.py -v
```

**Step 6: Commit**

```bash
git add scraper/threads.py tests/test_threads.py tests/fixtures/
git commit -m "feat: Threads 爬蟲模組，含嵌入 JSON 遞迴解析"
```

---

### Task 5: 圖片 OCR 模組（Claude Vision）

**Files:**
- Create: `media/ocr.py`
- Create: `tests/test_ocr.py`

**Step 1: 寫測試**

```python
# tests/test_ocr.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from media.ocr import extract_image_text, format_ocr_results


@pytest.mark.asyncio
@patch("media.ocr.get_anthropic_client")
async def test_extract_image_text_returns_text(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="這是圖片上的文字")]
    )
    mock_get_client.return_value = mock_client

    result = await extract_image_text("https://example.com/image.jpg")
    assert result == "這是圖片上的文字"


@pytest.mark.asyncio
@patch("media.ocr.get_anthropic_client")
async def test_extract_image_text_returns_empty_for_no_text(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="無文字")]
    )
    mock_get_client.return_value = mock_client

    result = await extract_image_text("https://example.com/photo.jpg")
    assert result == ""


def test_format_ocr_results_filters_empty():
    results = ["文字一", "", "文字二", ""]
    assert format_ocr_results(results) == "文字一\n\n文字二"


def test_format_ocr_results_returns_empty_for_all_empty():
    results = ["", "", ""]
    assert format_ocr_results(results) == ""
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_ocr.py -v
```

**Step 3: 實作 ocr.py**

```python
# media/ocr.py
import anthropic
from config import ANTHROPIC_API_KEY

_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


async def extract_image_text(image_url: str) -> str:
    """用 Claude Vision 擷取圖片上的文字"""
    client = get_anthropic_client()
    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "url", "url": image_url}},
                {"type": "text", "text": "請擷取這張圖片上的所有文字，保持原始排版。如果圖片上完全沒有文字，只回覆「無文字」。"},
            ],
        }],
    )
    text = response.content[0].text.strip()
    if text == "無文字":
        return ""
    return text


async def process_images(image_urls: list[str]) -> str:
    """處理多張圖片的 OCR，回傳合併結果"""
    results = []
    for url in image_urls:
        text = await extract_image_text(url)
        results.append(text)
    return format_ocr_results(results)


def format_ocr_results(results: list[str]) -> str:
    """合併 OCR 結果，過濾空值"""
    non_empty = [r for r in results if r.strip()]
    return "\n\n".join(non_empty)
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_ocr.py -v
```

**Step 5: Commit**

```bash
git add media/ocr.py tests/test_ocr.py
git commit -m "feat: 圖片 OCR 模組，用 Claude Vision 擷取圖片文字"
```

---

### Task 6: 影片逐字稿模組（ffmpeg + Whisper）

**Files:**
- Create: `media/transcriber.py`
- Create: `tests/test_transcriber.py`

**前置條件檢查：**

```bash
ffmpeg -version  # 確認 ffmpeg 已安裝
```

如未安裝：`brew install ffmpeg`

**Step 1: 寫測試**

```python
# tests/test_transcriber.py
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from media.transcriber import extract_audio, transcribe_audio


def test_extract_audio_creates_mp3(tmp_path):
    """測試 ffmpeg 音軌擷取（需要真實 ffmpeg）"""
    # 建立一個極小的測試用音檔（靜音）
    import subprocess

    video_path = tmp_path / "test.mp4"
    # 產生 1 秒靜音影片
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", "1", "-q:a", "9", "-acodec", "aac", str(video_path),
    ], capture_output=True)

    audio_path = extract_audio(video_path)
    assert audio_path.exists()
    assert audio_path.suffix == ".mp3"
    # 清理
    audio_path.unlink()
    video_path.unlink()


@pytest.mark.asyncio
@patch("media.transcriber.get_openai_client")
async def test_transcribe_audio_returns_text(mock_get_client):
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(text="大家好")
    mock_get_client.return_value = mock_client

    result = await transcribe_audio(Path("/fake/audio.mp3"))
    assert result == "大家好"
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_transcriber.py -v
```

**Step 3: 實作 transcriber.py**

```python
# media/transcriber.py
import subprocess
from pathlib import Path

import httpx
import openai

from config import OPENAI_API_KEY, TEMP_DIR

_client: openai.OpenAI | None = None


def get_openai_client() -> openai.OpenAI:
    global _client
    if _client is None:
        _client = openai.OpenAI(api_key=OPENAI_API_KEY)
    return _client


async def download_video(video_url: str) -> Path:
    """下載影片到暫存目錄"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    video_path = TEMP_DIR / "video.mp4"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120) as client:
        response = await client.get(video_url)
        response.raise_for_status()
        video_path.write_bytes(response.content)

    return video_path


def extract_audio(video_path: Path) -> Path:
    """用 ffmpeg 從影片擷取音軌為 MP3"""
    audio_path = video_path.with_suffix(".mp3")
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            str(audio_path),
        ],
        capture_output=True,
        check=True,
    )
    return audio_path


async def transcribe_audio(audio_path: Path) -> str:
    """用 OpenAI Whisper API 將音訊轉逐字稿"""
    client = get_openai_client()
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language="zh",
        )
    return transcript.text


async def process_video(video_url: str) -> str:
    """完整影片處理管線：下載 → 抽音軌 → 轉逐字稿 → 清理"""
    video_path = await download_video(video_url)
    try:
        audio_path = extract_audio(video_path)
        try:
            transcript = await transcribe_audio(audio_path)
            return transcript
        finally:
            audio_path.unlink(missing_ok=True)
    finally:
        video_path.unlink(missing_ok=True)
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_transcriber.py -v
```

**Step 5: Commit**

```bash
git add media/transcriber.py tests/test_transcriber.py
git commit -m "feat: 影片逐字稿模組，ffmpeg 抽音軌 + Whisper STT"
```

---

### Task 7: Google Sheet 讀寫模組

**Files:**
- Create: `services/sheet.py`
- Create: `tests/test_sheet.py`

**前置條件：** 需要 Google Cloud Service Account 的 `credentials.json`。參考設定步驟：
1. Google Cloud Console → 建專案 → 啟用 Google Sheets API + Google Drive API
2. 建立 Service Account → 下載 JSON 金鑰存為 `credentials.json`
3. 將 Service Account email 加為試算表的編輯者

**Step 1: 寫測試**

```python
# tests/test_sheet.py
import pytest
from unittest.mock import MagicMock, patch
from services.sheet import get_pending_rows, write_result


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_finds_empty_c_column(mock_ws):
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "原始內容", "AI 摘要"],          # 標題列
        ["https://instagram.com/p/abc", "", ""],       # 待處理
        ["https://threads.net/@user/post/xyz", "已有內容", "已有摘要"],  # 已處理
        ["https://instagram.com/p/def", "", ""],       # 待處理
        ["", "", ""],                                   # 空列
    ]
    pending = get_pending_rows()
    assert len(pending) == 2
    assert pending[0] == (2, "https://instagram.com/p/abc")
    assert pending[1] == (4, "https://instagram.com/p/def")


@patch("services.sheet.get_worksheet")
def test_write_result_updates_b_and_c_columns(mock_ws):
    mock_worksheet = MagicMock()
    mock_ws.return_value = mock_worksheet

    write_result(2, raw_content="原始文字", summary="AI 摘要")

    mock_worksheet.update_cell.assert_any_call(2, 2, "原始文字")
    mock_worksheet.update_cell.assert_any_call(2, 3, "AI 摘要")


@patch("services.sheet.get_worksheet")
def test_get_pending_rows_returns_empty_for_all_processed(mock_ws):
    mock_ws.return_value.get_all_values.return_value = [
        ["社群連結", "原始內容", "AI 摘要"],
        ["https://instagram.com/p/abc", "內容", "摘要"],
    ]
    pending = get_pending_rows()
    assert len(pending) == 0
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_sheet.py -v
```

**Step 3: 實作 sheet.py**

```python
# services/sheet.py
import gspread
from config import GOOGLE_SHEET_URL, GOOGLE_CREDENTIALS_PATH

_worksheet: gspread.Worksheet | None = None


def get_worksheet() -> gspread.Worksheet:
    global _worksheet
    if _worksheet is None:
        gc = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
        spreadsheet = gc.open_by_url(GOOGLE_SHEET_URL)
        _worksheet = spreadsheet.sheet1
    return _worksheet


def get_pending_rows() -> list[tuple[int, str]]:
    """找出 A 欄有值但 C 欄為空的列，回傳 (row_number, url) 列表"""
    ws = get_worksheet()
    rows = ws.get_all_values()

    pending = []
    for i, row in enumerate(rows[1:], start=2):  # 跳過標題列
        url = row[0].strip() if len(row) > 0 else ""
        summary = row[2].strip() if len(row) > 2 else ""
        if url and not summary:
            pending.append((i, url))
    return pending


def write_result(row_num: int, raw_content: str, summary: str) -> None:
    """將原始內容寫入 B 欄、摘要寫入 C 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 2, raw_content)
    ws.update_cell(row_num, 3, summary)


def write_error(row_num: int, error_msg: str) -> None:
    """將錯誤訊息寫入 C 欄"""
    ws = get_worksheet()
    ws.update_cell(row_num, 3, f"[ERROR] {error_msg}")
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_sheet.py -v
```

**Step 5: Commit**

```bash
git add services/sheet.py tests/test_sheet.py
git commit -m "feat: Google Sheet 讀寫模組，支援待處理列偵測與結果回寫"
```

---

### Task 8: LLM 摘要模組

**Files:**
- Create: `services/summarizer.py`
- Create: `tests/test_summarizer.py`

**Step 1: 寫測試**

```python
# tests/test_summarizer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.summarizer import summarize, format_raw_content


def test_format_raw_content_with_all_fields():
    result = format_raw_content(
        caption="這是貼文",
        ocr_text="圖片文字",
        transcript="影片逐字稿",
    )
    assert "【貼文文字】" in result
    assert "這是貼文" in result
    assert "【圖片文字】" in result
    assert "圖片文字" in result
    assert "【影片逐字稿】" in result
    assert "影片逐字稿" in result


def test_format_raw_content_omits_empty_fields():
    result = format_raw_content(caption="只有文字", ocr_text="", transcript="")
    assert "【貼文文字】" in result
    assert "【圖片文字】" not in result
    assert "【影片逐字稿】" not in result


def test_format_raw_content_empty_caption():
    result = format_raw_content(caption="", ocr_text="圖片文字", transcript="")
    assert "【貼文文字】" not in result
    assert "【圖片文字】" in result


@pytest.mark.asyncio
@patch("services.summarizer.get_anthropic_client")
async def test_summarize_returns_text(mock_get_client):
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="這是 AI 摘要")]
    )
    mock_get_client.return_value = mock_client

    result = await summarize("一些原始內容")
    assert result == "這是 AI 摘要"
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_summarizer.py -v
```

**Step 3: 實作 summarizer.py**

```python
# services/summarizer.py
import anthropic
from config import ANTHROPIC_API_KEY

_client: anthropic.AsyncAnthropic | None = None


def get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def format_raw_content(caption: str, ocr_text: str, transcript: str) -> str:
    """將各來源內容格式化為 B 欄格式"""
    sections = []
    if caption.strip():
        sections.append(f"【貼文文字】\n{caption.strip()}")
    if ocr_text.strip():
        sections.append(f"【圖片文字】\n{ocr_text.strip()}")
    if transcript.strip():
        sections.append(f"【影片逐字稿】\n{transcript.strip()}")
    return "\n\n".join(sections)


async def summarize(raw_content: str) -> str:
    """用 Claude Sonnet 產出摘要"""
    client = get_anthropic_client()
    response = await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                "請用繁體中文摘要以下社群貼文內容，"
                "包含重點觀點和關鍵資訊，控制在 2-3 句話：\n\n"
                f"{raw_content}"
            ),
        }],
    )
    return response.content[0].text.strip()
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_summarizer.py -v
```

**Step 5: Commit**

```bash
git add services/summarizer.py tests/test_summarizer.py
git commit -m "feat: LLM 摘要模組，含原始內容格式化與 Claude Sonnet 摘要"
```

---

### Task 9: 主控流程（Orchestrator）

**Files:**
- Create: `main.py`
- Create: `tests/test_main.py`

**Step 1: 寫測試**

```python
# tests/test_main.py
import pytest
from main import detect_platform


def test_detect_platform_instagram():
    assert detect_platform("https://www.instagram.com/p/abc123/") == "instagram"
    assert detect_platform("https://instagram.com/reel/abc123/") == "instagram"


def test_detect_platform_threads():
    assert detect_platform("https://www.threads.net/@user/post/abc123") == "threads"


def test_detect_platform_unknown():
    with pytest.raises(ValueError, match="不支援的平台"):
        detect_platform("https://twitter.com/post/123")
```

**Step 2: 跑測試確認失敗**

```bash
uv run pytest tests/test_main.py -v
```

**Step 3: 實作 main.py**

```python
# main.py
import asyncio
import logging
import random

from config import DAILY_LIMIT, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from scraper.browser import create_browser
from scraper.instagram import scrape_instagram, PostData
from scraper.threads import scrape_threads
from media.ocr import process_images
from media.transcriber import process_video
from services.sheet import get_pending_rows, write_result, write_error
from services.summarizer import summarize, format_raw_content

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    elif "threads.net" in url:
        return "threads"
    else:
        raise ValueError(f"不支援的平台: {url}")


async def process_post(context, url: str) -> tuple[str, str]:
    """處理單篇貼文：爬取 → 媒體處理 → 摘要，回傳 (raw_content, summary)"""
    platform = detect_platform(url)

    # 爬取
    if platform == "instagram":
        post = await scrape_instagram(context, url)
    else:
        post = await scrape_threads(context, url)

    # 媒體處理
    ocr_text = ""
    if post.image_urls:
        ocr_text = await process_images(post.image_urls)

    transcript = ""
    if post.video_url:
        transcript = await process_video(post.video_url)

    # 格式化原始內容
    raw_content = format_raw_content(
        caption=post.caption,
        ocr_text=ocr_text,
        transcript=transcript,
    )

    # 摘要
    summary = await summarize(raw_content)

    return raw_content, summary


async def main():
    pending = get_pending_rows()
    if not pending:
        logger.info("沒有待處理的 URL")
        return

    # 每日上限
    pending = pending[:DAILY_LIMIT]
    logger.info(f"待處理 {len(pending)} 筆")

    browser, context = await create_browser()
    try:
        for row_num, url in pending:
            logger.info(f"處理第 {row_num} 列: {url}")
            try:
                raw_content, summary = await process_post(context, url)
                write_result(row_num, raw_content, summary)
                logger.info(f"第 {row_num} 列完成")
            except Exception as e:
                logger.error(f"第 {row_num} 列失敗: {e}")
                write_error(row_num, str(e))

            # 隨機延遲
            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            logger.info(f"等待 {delay:.1f} 秒")
            await asyncio.sleep(delay)
    finally:
        await browser.close()

    logger.info("全部完成")


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: 跑測試確認通過**

```bash
uv run pytest tests/test_main.py -v
```

**Step 5: Commit**

```bash
git add main.py tests/test_main.py
git commit -m "feat: 主控流程，串接爬蟲、媒體處理、摘要與 Sheet 讀寫"
```

---

### Task 10: 端對端整合測試

**Files:**
- Create: `tests/test_integration.py`

**前置條件：**
- `.env` 已設定所有 API key
- `credentials.json` 已就位
- Google Sheet 已建立，A1 = "社群連結"、B1 = "原始內容"、C1 = "AI 摘要"
- A2 填入一個公開 IG 貼文 URL
- A3 填入一個公開 Threads 貼文 URL

**Step 1: 寫整合測試**

```python
# tests/test_integration.py
"""
端對端整合測試。
需要真實的 API key 和 Google Sheet。
用 pytest -m integration 執行。
"""
import pytest
import asyncio
from main import process_post, detect_platform
from scraper.browser import create_browser


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scrape_real_ig_post():
    """測試真實 IG 公開貼文的爬取"""
    browser, context = await create_browser()
    try:
        # 替換為一個已知的公開 IG 貼文 URL
        url = "https://www.instagram.com/p/REAL_POST_ID/"
        raw_content, summary = await process_post(context, url)
        assert len(raw_content) > 0
        assert len(summary) > 0
        print(f"\n--- Raw ---\n{raw_content}\n--- Summary ---\n{summary}")
    finally:
        await browser.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scrape_real_threads_post():
    """測試真實 Threads 公開貼文的爬取"""
    browser, context = await create_browser()
    try:
        # 替換為一個已知的公開 Threads 貼文 URL
        url = "https://www.threads.net/@REAL_USER/post/REAL_POST_ID"
        raw_content, summary = await process_post(context, url)
        assert len(raw_content) > 0
        assert len(summary) > 0
        print(f"\n--- Raw ---\n{raw_content}\n--- Summary ---\n{summary}")
    finally:
        await browser.close()
```

**Step 2: 先跑單元測試確認全部通過**

```bash
uv run pytest tests/ -v --ignore=tests/test_integration.py
```

預期：全部 PASS

**Step 3: 跑整合測試（需要真實 API key）**

```bash
uv run pytest tests/test_integration.py -v -m integration -s
```

觀察輸出，確認：
1. IG 貼文能成功取得 caption
2. Threads 貼文能成功取得 caption
3. 摘要有合理內容

**Step 4: 用 main.py 做完整端對端測試**

在 Google Sheet A2 填入一個公開 IG 貼文 URL，然後：

```bash
uv run python main.py
```

確認：
- B2 出現原始內容（含【貼文文字】標記）
- C2 出現 AI 摘要

**Step 5: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 端對端整合測試"
```

---

## 任務摘要

| Task | 內容 | 預估 |
|------|------|------|
| 1 | 專案骨架與依賴 | 10 min |
| 2 | 瀏覽器管理模組 | 15 min |
| 3 | Instagram 爬蟲（含 spike） | 30 min |
| 4 | Threads 爬蟲（含 spike） | 30 min |
| 5 | 圖片 OCR | 15 min |
| 6 | 影片逐字稿 | 15 min |
| 7 | Google Sheet 讀寫 | 15 min |
| 8 | LLM 摘要 | 10 min |
| 9 | 主控流程 | 15 min |
| 10 | 端對端整合測試 | 20 min |

**前置條件 checklist：**
- [ ] `ffmpeg` 已安裝（`brew install ffmpeg`）
- [ ] Google Cloud Service Account 已建立，`credentials.json` 已下載
- [ ] Google Sheet 已建立並共享給 Service Account
- [ ] `.env` 已填入 ANTHROPIC_API_KEY、OPENAI_API_KEY、GOOGLE_SHEET_URL
- [ ] Patchright 瀏覽器已安裝（`uv run patchright install chromium`）
