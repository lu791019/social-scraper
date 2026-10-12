import asyncio
import logging
import random
from dataclasses import dataclass

from config import DAILY_LIMIT, REQUEST_DELAY_MIN, REQUEST_DELAY_MAX
from scraper.browser import create_browser, close_browser, explain_navigation_error
from scraper.instagram import scrape_instagram
from scraper.threads import scrape_threads
from scraper.github import fetch_repo
from media.ocr import process_images
from media.transcriber import process_video
from services.sheet import (
    get_pending_rows, write_result, write_error,
    get_github_pending_rows, write_github_result, write_github_error,
)
from services.summarizer import PostSummary, summarize_post, format_raw_content
from services.discord_sink import DiscordPost, send_post_to_discord
from services.github_summarizer import summarize_readme

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# httpx 的 INFO log 會印出完整請求網址（含 Discord webhook token），只留 WARNING 以上
logging.getLogger("httpx").setLevel(logging.WARNING)
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


@dataclass(frozen=True)
class ProcessedPost:
    url: str
    platform: str
    author: str
    first_image: str | None
    summary: PostSummary
    warnings: tuple[str, ...] = ()


async def process_post_detailed(context, url: str) -> ProcessedPost:
    """處理單篇貼文：爬取 → 媒體處理 → 摘要+關鍵點+Discord 點評，回傳完整結果"""
    platform = detect_platform(url)

    if platform == "instagram":
        post = await scrape_instagram(context, url)
    else:
        post = await scrape_threads(context, url)

    warnings: list[str] = []
    ocr_text = await _try_media(post.image_urls and process_images(post.image_urls), "圖片 OCR", warnings)
    transcript = await _try_media(post.video_url and process_video(post.video_url), "影片逐字稿", warnings)

    raw_content = format_raw_content(
        caption=post.caption,
        ocr_text=ocr_text,
        transcript=transcript,
    )
    if not raw_content.strip():
        raise RuntimeError("沒有可摘要的內容：" + ("；".join(warnings) or "貼文無文字與媒體"))

    summary = await summarize_post(raw_content)
    return ProcessedPost(
        url=url,
        platform=platform,
        author=post.author,
        first_image=post.image_urls[0] if post.image_urls else None,
        summary=summary,
        warnings=tuple(warnings),
    )


async def _try_media(job, label: str, warnings: list[str]) -> str:
    """媒體處理失敗不擋整篇：記 log 並把警告帶回呼叫端顯示（不靜默降級）"""
    if not job:
        return ""
    try:
        return await job
    except Exception as e:
        logger.error(f"{label}失敗，改用貼文文字繼續：{e}")
        reason = explain_navigation_error(e) or str(e)[:80]
        warnings.append(f"{label}失敗：{reason}；摘要只根據貼文文字")
        return ""


async def process_post(context, url: str) -> tuple[str, str]:
    """Sheet 用的舊介面：回傳 (summary, key_points)"""
    result = await process_post_detailed(context, url)
    return result.summary.summary, result.summary.key_points


def to_discord_post(result: ProcessedPost) -> DiscordPost:
    return DiscordPost(
        url=result.url,
        platform=result.platform,
        author=result.author,
        title=result.summary.title,
        summary=result.summary.summary,
        key_points=result.summary.key_points,
        comment=result.summary.discord_comment,
        image_url=result.first_image,
    )


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
                result = await process_post_detailed(context, url)
                write_result(row_num, result.summary.summary, result.summary.key_points)
                logger.info(f"第 {row_num} 列完成" + (f"（警告：{'；'.join(result.warnings)}）" if result.warnings else ""))
                await send_post_to_discord(to_discord_post(result))
            except Exception as e:
                logger.error(f"第 {row_num} 列失敗: {e}")
                write_error(row_num, str(e))

            delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
            logger.info(f"等待 {delay:.1f} 秒")
            await asyncio.sleep(delay)
    finally:
        await close_browser(browser)

    logger.info("全部完成")


if __name__ == "__main__":
    asyncio.run(main())
