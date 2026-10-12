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

# browser → 啟動它的 Playwright driver，close_browser 時一起停掉
_drivers: dict[int, object] = {}

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


_BLOCKED_MARKERS = ("ERR_CERT_AUTHORITY_INVALID", "ERR_CERT_COMMON_NAME_INVALID", "CERTIFICATE_VERIFY_FAILED")


def explain_navigation_error(exc: Exception) -> str | None:
    """把「網路層攔截」類錯誤翻成可讀訊息；其他錯誤回 None 照原樣拋。"""
    text = str(exc)
    if any(marker in text for marker in _BLOCKED_MARKERS):
        return ("目前網路攔截了這個網站的 SSL 連線（常見於公司／教室防火牆，例如 FortiGate 封鎖社群網站），"
                "請換網路（如手機熱點）再試")
    return None


async def goto(page: Page, url: str, timeout_ms: int) -> None:
    """page.goto 包一層：網路封鎖時拋出可讀的 RuntimeError"""
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
    except Exception as e:
        reason = explain_navigation_error(e)
        if reason:
            raise RuntimeError(reason) from e
        raise


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
    _drivers[id(browser)] = pw
    return browser, context


async def close_browser(browser: Browser) -> None:
    """關閉瀏覽器並停止 Patchright driver（只關 browser 會殘留 driver 行程）"""
    pw = _drivers.pop(id(browser), None)
    try:
        await browser.close()
    finally:
        if pw is not None:
            await pw.stop()
