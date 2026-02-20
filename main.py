import asyncio
import logging
import random

from config import DAILY_LIMIT, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from scraper.browser import create_browser
from scraper.instagram import scrape_instagram
from scraper.threads import scrape_threads
from media.ocr import process_images
from media.transcriber import process_video
from services.sheet import get_pending_rows, write_result, write_error
from services.summarizer import summarize, extract_key_points, format_raw_content

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    elif "threads.net" in url or "threads.com" in url:
        return "threads"
    else:
        raise ValueError(f"不支援的平台: {url}")


async def process_post(context, url: str) -> tuple[str, str]:
    """處理單篇貼文：爬取 → 媒體處理 → 摘要+關鍵點，回傳 (summary, key_points)"""
    platform = detect_platform(url)

    if platform == "instagram":
        post = await scrape_instagram(context, url)
    else:
        post = await scrape_threads(context, url)

    ocr_text = ""
    if post.image_urls:
        ocr_text = await process_images(post.image_urls)

    transcript = ""
    if post.video_url:
        transcript = await process_video(post.video_url)

    raw_content = format_raw_content(
        caption=post.caption,
        ocr_text=ocr_text,
        transcript=transcript,
    )

    summary = await summarize(raw_content)
    key_points = await extract_key_points(raw_content)

    return summary, key_points


async def main():
    pending = get_pending_rows()
    if not pending:
        logger.info("沒有待處理的 URL")
        return

    pending = pending[:DAILY_LIMIT]
    logger.info(f"待處理 {len(pending)} 筆")

    browser, context = await create_browser()
    try:
        for row_num, url in pending:
            logger.info(f"處理第 {row_num} 列: {url}")
            try:
                summary, key_points = await process_post(context, url)
                write_result(row_num, summary, key_points)
                logger.info(f"第 {row_num} 列完成")
            except Exception as e:
                logger.error(f"第 {row_num} 列失敗: {e}")
                write_error(row_num, str(e))

            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            logger.info(f"等待 {delay:.1f} 秒")
            await asyncio.sleep(delay)
    finally:
        await browser.close()

    logger.info("全部完成")


if __name__ == "__main__":
    asyncio.run(main())
