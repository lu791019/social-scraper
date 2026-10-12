"""單筆工作的處理流程（Mac 工作程式用；不含任何 LINE／佇列邏輯）。

成功回傳 JobOutcome（LINE 訊息 + 回寫雲端的 result）；失敗直接拋例外，由呼叫端決定重試。
寫 Sheet 放在處理成功之後，重試不會產生重複列。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SUMMARY_PREVIEW = 200


@dataclass(frozen=True)
class JobOutcome:
    message: str
    result: dict = field(default_factory=dict)


async def process_social(url: str) -> JobOutcome:
    from main import process_post_detailed, to_discord_post
    from scraper.browser import close_browser, create_browser
    from services.discord_sink import send_post_to_discord
    from services.sheet import append_url, write_result

    browser, context = await create_browser()
    try:
        processed = await process_post_detailed(context, url)
    finally:
        await close_browser(browser)

    s = processed.summary
    row = append_url(url)
    write_result(row, s.summary, s.key_points)
    discord_ok = await send_post_to_discord(to_discord_post(processed))

    notes = [f"⚠️ {w}" for w in processed.warnings]
    if not discord_ok:
        notes.append("⚠️ Discord 未送出（見 logs）")
    message = f"✅ 完成（Sheet 第 {row} 列）\n{url}\n\n📝 {s.summary[:SUMMARY_PREVIEW]}" + "".join(f"\n{n}" for n in notes)
    return JobOutcome(message, {
        "sheet_row": row, "title": s.title, "summary": s.summary, "key_points": s.key_points,
        "discord_comment": s.discord_comment, "discord_sent": discord_ok, "warnings": list(processed.warnings),
        "author": processed.author,
    })


async def process_github(url: str) -> JobOutcome:
    from scraper.github import fetch_repo
    from services.github_summarizer import summarize_readme
    from services.sheet import append_github_repo, write_github_result

    repo = await fetch_repo(url)
    summary, use_cases = await summarize_readme(repo)
    stars_lang = f"⭐ {repo.stars} | {repo.language}" if repo.language else f"⭐ {repo.stars}"
    row = append_github_repo(url)
    write_github_result(row, repo.full_name, repo.description, summary, use_cases, stars_lang)
    return JobOutcome(
        f"✅ GitHub 完成（第 {row} 列）\n📦 {repo.full_name}\n📝 {summary[:SUMMARY_PREVIEW]}",
        {"sheet_row": row, "repo": repo.full_name, "summary": summary},
    )


async def process_article(url: str) -> JobOutcome:
    from scraper.article import scrape_article
    from services.notion import create_article_page

    article = await scrape_article(url)
    page_url = create_article_page(article)
    return JobOutcome(f"✅ 已存入 Notion：{article.title}\n👉 {page_url}",
                      {"title": article.title, "notion_url": page_url})


PROCESSORS = {
    "instagram": process_social,
    "threads": process_social,
    "github": process_github,
    "article": process_article,
}


async def run_job(platform: str, url: str) -> JobOutcome:
    processor = PROCESSORS.get(platform)
    if processor is None:
        raise ValueError(f"不支援的平台：{platform}")
    return await processor(url)


def record_final_error(platform: str, url: str, error: str) -> None:
    """重試用完才寫 Sheet 錯誤列（與舊版行為一致：B 欄 [ERROR]）；寫失敗只記 log。"""
    try:
        if platform in ("instagram", "threads"):
            from services.sheet import append_url, write_error
            write_error(append_url(url), error)
        elif platform == "github":
            from services.sheet import append_github_repo, write_github_error
            write_github_error(append_github_repo(url), error)
    except Exception as e:
        logger.error(f"寫 Sheet 錯誤列失敗：{e}")
