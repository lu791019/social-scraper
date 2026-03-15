import asyncio
import logging

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
from linebot.line_handler import extract_urls
from services.sheet import append_url

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
handler = WebhookHandler(LINE_CHANNEL_SECRET)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)


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

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent):
    text = event.message.text
    urls = extract_urls(text)

    if not urls:
        reply_text(event.reply_token, "請傳送 Instagram 或 Threads 的貼文連結。")
        return

    results = []
    for url in urls:
        row_num = append_url(url)
        results.append(f"✅ {url}\n   → 第 {row_num} 列")

        # 背景觸發 scraper
        user_id = event.source.user_id
        asyncio.get_event_loop().create_task(
            run_scraper_for_url(user_id, url, row_num)
        )

    reply_msg = "已收到，處理中...\n\n" + "\n".join(results)
    reply_text(event.reply_token, reply_msg)
