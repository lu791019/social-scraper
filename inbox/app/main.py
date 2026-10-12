"""social-scraper-inbox：只收件、不爬不跑 AI。

POST /callback          LINE webhook：驗簽 → 抽連結 → 入列 → 回「收到，處理中」
POST /jobs/claim        Mac 工作程式拉一筆（Bearer worker_key）；沒有工作回 204
POST /jobs/{id}/done    回寫結果或錯誤（Bearer worker_key）；重送是 no-op
GET  /health
"""
from __future__ import annotations

import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from pydantic import BaseModel

from app.config import Settings, load_settings
from app.db import JobStore
from app.line import extract_links, reply_text, verify_signature

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger("inbox")

STATUS_COMMANDS = {"進度", "狀態", "status"}
PLATFORM_LABELS = {"instagram": "IG", "threads": "Threads", "github": "GitHub", "article": "網頁"}


class DoneRequest(BaseModel):
    success: bool
    result: dict | None = None
    error: str | None = None


def create_app(settings: Settings | None = None, store: JobStore | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings or load_settings()
        s = app.state.settings
        app.state.store = store or JobStore(s.database_url, s.max_attempts, s.lease_minutes)
        app.state.store.ensure_schema()
        yield
        if store is None:
            app.state.store.close()

    app = FastAPI(title="social-scraper-inbox", lifespan=lifespan)

    def require_worker(request: Request, authorization: str = Header(default="")) -> None:
        expected = f"Bearer {request.app.state.settings.worker_key}"
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/callback")
    async def callback(request: Request, x_line_signature: str = Header(default="")):
        body = await request.body()
        s: Settings = request.app.state.settings
        if not verify_signature(s.line_channel_secret, body, x_line_signature):
            logger.warning("LINE 簽章驗證失敗")
            raise HTTPException(status_code=400, detail="invalid signature")
        try:
            events = json.loads(body).get("events", [])
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid body")
        for event in events:
            _handle_event(request.app.state.store, s, event)
        return {"status": "ok"}

    @app.post("/jobs/claim", dependencies=[Depends(require_worker)])
    def claim(request: Request):
        job = request.app.state.store.claim()
        if job is None:
            return Response(status_code=204)
        logger.info(f"claim job {job.id}（第 {job.attempts} 次）")
        return job.to_dict()

    @app.post("/jobs/{job_id}/done", dependencies=[Depends(require_worker)])
    def done(job_id: int, req: DoneRequest, request: Request):
        job, changed = request.app.state.store.finish(job_id, req.success, req.result, req.error)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        logger.info(f"done job {job.id} → {job.status}{'' if changed else '（重送，未變動）'}")
        return {**job.to_dict(), "changed": changed}

    return app


def _handle_event(store: JobStore, s: Settings, event: dict) -> None:
    message = event.get("message") or {}
    if event.get("type") != "message" or message.get("type") != "text":
        return
    text = message.get("text", "")
    reply_token = event.get("replyToken", "")
    user_id = (event.get("source") or {}).get("userId")

    if text.strip() in STATUS_COMMANDS:
        reply_text(s.line_channel_access_token, reply_token, f"📊 排隊中＋處理中：{store.pending_count()} 筆")
        return

    links = extract_links(text)
    if not links:
        reply_text(s.line_channel_access_token, reply_token, "請傳送 Instagram、Threads、GitHub 或網頁連結。")
        return

    jobs = store.enqueue(links, user_id)
    lines = [f"• {PLATFORM_LABELS[j.platform]}：{j.url}" for j in jobs]
    reply_text(
        s.line_channel_access_token, reply_token,
        f"收到 {len(jobs)} 筆，處理中 🐍\n" + "\n".join(lines) + "\n\n完成後會再通知你（Mac 關機時會排隊，開機後補做）。",
    )
    logger.info(f"入列 {len(jobs)} 筆：{[j.id for j in jobs]}")


app = create_app()
