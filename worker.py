"""Mac 工作程式（launchd: com.dex.social-scraper.worker）。

每 WORKER_POLL_SECONDS 秒向雲端收件服務 claim 一筆 → 跑既有流程 → done 回寫 → LINE push 回報。
有工作時連續處理到佇列清空；Mac 關機期間雲端照常排隊，開機後自動補做。
"""
from __future__ import annotations

import asyncio
import logging
import time

import httpx

from config import INBOX_URL, INBOX_WORKER_KEY, WORKER_POLL_SECONDS
from services.line_push import push_text
from services.pipeline import record_final_error, run_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# httpx 的 INFO log 會印出完整請求網址（含 Discord webhook token），只留 WARNING 以上
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("worker")

DONE_RETRIES = 5
DONE_BACKOFF_S = 5.0
ERROR_PREVIEW = 300


class InboxClient:
    def __init__(self, base_url: str, worker_key: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=30, transport=transport,
            headers={"Authorization": f"Bearer {worker_key}"},
        )

    def claim(self) -> dict | None:
        resp = self._client.post("/jobs/claim")
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        return resp.json()

    def done(self, job_id: int, success: bool, result: dict | None = None, error: str | None = None,
             retries: int = DONE_RETRIES, backoff_s: float = DONE_BACKOFF_S) -> dict:
        payload = {"success": success, "result": result, "error": error}
        for attempt in range(1, retries + 1):
            try:
                resp = self._client.post(f"/jobs/{job_id}/done", json=payload)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as e:
                logger.warning(f"done 回寫失敗（{attempt}/{retries}）：{type(e).__name__}")
                if attempt == retries:
                    raise
                time.sleep(backoff_s * attempt)
        raise RuntimeError("unreachable")


async def handle_job(job: dict, inbox: InboxClient) -> str:
    """處理一筆並回寫；回傳最終狀態（done / queued / error）。"""
    job_id, url, platform, user = job["id"], job["url"], job["platform"], job.get("line_user_id")
    logger.info(f"開始 job {job_id}（{platform}，第 {job['attempts']} 次）：{url}")
    try:
        outcome = await run_job(platform, url)
    except Exception as e:
        error = f"{type(e).__name__}: {e}"[:ERROR_PREVIEW]
        logger.error(f"job {job_id} 失敗：{error}")
        state = inbox.done(job_id, False, error=error)
        if state["status"] == "error":
            record_final_error(platform, url, error)
            push_text(user, f"❌ 處理失敗（已試 {state['attempts']} 次，不再重試）\n{url}\n\n{error}")
        return state["status"]

    state = inbox.done(job_id, True, result=outcome.result)
    if state.get("changed", True):
        push_text(user, outcome.message)
    logger.info(f"job {job_id} 完成")
    return state["status"]


async def drain(inbox: InboxClient) -> int:
    """連續 claim 到沒有工作為止，回傳處理筆數。"""
    handled = 0
    while (job := inbox.claim()) is not None:
        await handle_job(job, inbox)
        handled += 1
    return handled


async def run_forever(inbox: InboxClient, interval_s: float) -> None:
    logger.info(f"worker 啟動，輪詢 {INBOX_URL}，間隔 {interval_s:.0f} 秒")
    while True:
        try:
            n = await drain(inbox)
            if n:
                logger.info(f"本輪處理 {n} 筆")
        except httpx.HTTPError as e:
            logger.warning(f"連不到收件服務：{type(e).__name__}，{interval_s:.0f} 秒後再試")
        await asyncio.sleep(interval_s)


def main() -> None:
    if not INBOX_URL or not INBOX_WORKER_KEY:
        raise SystemExit("缺少 INBOX_URL 或 INBOX_WORKER_KEY（.env）")
    asyncio.run(run_forever(InboxClient(INBOX_URL, INBOX_WORKER_KEY), WORKER_POLL_SECONDS))


if __name__ == "__main__":
    main()
