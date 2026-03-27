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
