import asyncio
import logging
import random

from config import DAILY_LIMIT, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from scraper.browser import create_browser
from scraper.instagram import scrape_instagram
from scraper.threads import scrape_threads
from scraper.github import fetch_repo
from media.ocr import process_images
from media.transcriber import process_video
from services.sheet import (
    get_pending_rows, write_result, write_error,
    get_github_pending_rows, write_github_result, write_github_error,
)
from services.summarizer import summarize_and_extract, format_raw_content
from services.github_summarizer import summarize_readme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def detect_platform(url: str) -> str:
    if "github.com" in url:
        return "github"
    elif "instagram.com" in url:
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

    summary, key_points = await summarize_and_extract(raw_content)

    return summary, key_points


async def process_github_repos() -> None:
    """批次處理 GitHub 工作表中待處理的 repo"""
    pending = get_github_pending_rows()
    if not pending:
        logger.info("GitHub：沒有待處理的 URL")
        return

    pending = pending[:DAILY_LIMIT]
    logger.info(f"GitHub：待處理 {len(pending)} 筆")

    for row_num, url in pending:
        logger.info(f"GitHub 處理第 {row_num} 列: {url}")
        try:
            repo = await fetch_repo(url)
            summary, use_cases = await summarize_readme(repo)
            stars_lang = f"⭐ {repo.stars} | {repo.language}" if repo.language else f"⭐ {repo.stars}"
            write_github_result(row_num, repo.full_name, repo.description, summary, use_cases, stars_lang)
            logger.info(f"GitHub 第 {row_num} 列完成")
        except Exception as e:
            logger.error(f"GitHub 第 {row_num} 列失敗: {e}")
            write_github_error(row_num, str(e))


async def main():
    # 處理 GitHub 工作表
    await process_github_repos()

    # 處理社群貼文工作表
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
