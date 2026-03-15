import asyncio
import logging
import traceback

from fastapi import FastAPI, Request, HTTPException

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from config import LINE_CHANNEL_SECRET, LINE_CHANNEL_ACCESS_TOKEN
from line_webhook.line_handler import extract_urls, extract_github_urls
from services.sheet import append_url, append_github_repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# 用來從同步 handler 排程 async task
_loop: asyncio.AbstractEventLoop | None = None


@app.on_event("startup")
async def startup():
    global _loop
    _loop = asyncio.get_running_loop()


def reply_text(reply_token: str, text: str) -> None:
    """同步回覆文字訊息"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def push_text(user_id: str, text: str) -> None:
    """主動推播文字訊息給使用者"""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)],
            )
        )


async def run_scraper_for_url(user_id: str, url: str, row_num: int) -> None:
    """背景執行 scraper：爬取 → 摘要 → 寫回 Sheet → 推播結果"""
    try:
        from scraper.browser import create_browser
        from main import process_post
        from services.sheet import write_result

        browser, context = await create_browser()
        try:
            summary, key_points = await process_post(context, url)
            write_result(row_num, summary, key_points)
            push_text(user_id, f"處理完成！\n\n📝 摘要：{summary[:200]}")
        finally:
            await browser.close()
    except Exception as e:
        logger.error(f"背景 scraper 失敗 (row {row_num}): {e}")
        push_text(user_id, f"處理失敗：{e}")


@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = (await request.body()).decode("utf-8")
    logger.info(f"收到 webhook: {body[:200]}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Handler error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

    return "OK"


async def run_github_scraper(user_id: str, url: str, row_num: int) -> None:
    """背景執行 GitHub scraper：API 取得 → 摘要 → 寫回 Sheet → 推播"""
    try:
        from scraper.github import fetch_repo
        from services.github_summarizer import summarize_readme
        from services.sheet import write_github_result, write_github_error

        repo = await fetch_repo(url)
        summary, use_cases = await summarize_readme(repo)
        stars_lang = f"⭐ {repo.stars} | {repo.language}" if repo.language else f"⭐ {repo.stars}"
        write_github_result(row_num, repo.full_name, repo.description, summary, use_cases, stars_lang)
        push_text(user_id, f"GitHub 處理完成！\n\n📦 {repo.full_name}\n📝 {summary[:200]}")
    except Exception as e:
        logger.error(f"GitHub scraper 失敗 (row {row_num}): {e}")
        try:
            from services.sheet import write_github_error
            write_github_error(row_num, str(e))
        except Exception:
            pass
        push_text(user_id, f"GitHub 處理失敗：{e}")


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    try:
        text = event.message.text
        logger.info(f"收到訊息: {text}")

        github_urls = extract_github_urls(text)
        urls = extract_urls(text)

        if not urls and not github_urls:
            reply_text(event.reply_token, "請傳送 Instagram、Threads 或 GitHub 的連結。")
            return

        results = []
        user_id = event.source.user_id

        for url in github_urls:
            row_num = append_github_repo(url)
            results.append(f"📦 {url}\n   → GitHub 工作表第 {row_num} 列")
            logger.info(f"GitHub URL 寫入 Sheet 第 {row_num} 列: {url}")
            if _loop:
                _loop.create_task(run_github_scraper(user_id, url, row_num))

        for url in urls:
            row_num = append_url(url)
            results.append(f"✅ {url}\n   → 第 {row_num} 列")
            logger.info(f"URL 寫入 Sheet 第 {row_num} 列: {url}")
            if _loop:
                _loop.create_task(run_scraper_for_url(user_id, url, row_num))

        reply_msg = "已收到，處理中...\n\n" + "\n".join(results)
        reply_text(event.reply_token, reply_msg)
    except Exception as e:
        logger.error(f"handle_message 錯誤: {traceback.format_exc()}")
        try:
            reply_text(event.reply_token, f"處理發生錯誤：{e}")
        except Exception:
            pass
