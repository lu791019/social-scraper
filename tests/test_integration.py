"""
端對端整合測試。
需要真實的 Google Sheet 和 claude CLI。
用 pytest -m integration 執行。
"""
import pytest
from main import process_post, detect_platform
from scraper.browser import create_browser


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scrape_real_ig_post():
    """測試真實 IG 公開貼文的爬取"""
    browser, context = await create_browser()
    try:
        url = "https://www.instagram.com/p/DU3ijLaEiw_/"
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
        url = "https://www.threads.net/@natgeo/post/DU8qr-5kVWm"
        raw_content, summary = await process_post(context, url)
        assert len(raw_content) > 0
        assert len(summary) > 0
        print(f"\n--- Raw ---\n{raw_content}\n--- Summary ---\n{summary}")
    finally:
        await browser.close()
