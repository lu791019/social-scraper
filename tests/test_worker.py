"""Mac 工作程式：claim → 處理 → done → LINE push；失敗重試語意與網路錯誤。"""
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import worker
from services.pipeline import JobOutcome

JOB = {"id": 7, "url": "https://www.threads.com/@a/post/X", "platform": "threads",
       "line_user_id": "U1", "attempts": 1}


def _inbox(queue: list, done_status: str = "done", calls: list | None = None, done_fail_times: int = 0):
    state = {"done_fail": done_fail_times}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        if request.url.path == "/jobs/claim":
            return httpx.Response(200, json=queue.pop(0)) if queue else httpx.Response(204)
        if state["done_fail"] > 0:
            state["done_fail"] -= 1
            return httpx.Response(503)
        body = json.loads(request.content)
        if calls is not None:
            calls.append(body)
        return httpx.Response(200, json={**JOB, "status": done_status if not body["success"] else "done",
                                         "attempts": 3 if done_status == "error" else 1, "changed": True})
    return worker.InboxClient("https://inbox.test", "k", transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_success_reports_done_and_pushes():
    calls: list = []
    with patch("worker.run_job", AsyncMock(return_value=JobOutcome("✅ ok", {"sheet_row": 3}))), \
         patch("worker.push_text") as push:
        status = await worker.handle_job(JOB, _inbox([], calls=calls))
    assert status == "done"
    assert calls == [{"success": True, "result": {"sheet_row": 3}, "error": None}]
    push.assert_called_once_with("U1", "✅ ok")


@pytest.mark.asyncio
async def test_failure_requeued_does_not_push():
    with patch("worker.run_job", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("worker.push_text") as push, patch("worker.record_final_error") as rec:
        status = await worker.handle_job(JOB, _inbox([], done_status="queued"))
    assert status == "queued"
    push.assert_not_called()
    rec.assert_not_called()


@pytest.mark.asyncio
async def test_final_failure_pushes_and_records():
    with patch("worker.run_job", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("worker.push_text") as push, patch("worker.record_final_error") as rec:
        status = await worker.handle_job(JOB, _inbox([], done_status="error"))
    assert status == "error"
    assert "不再重試" in push.call_args.args[1] and "boom" in push.call_args.args[1]
    rec.assert_called_once()


@pytest.mark.asyncio
async def test_drain_processes_until_empty():
    with patch("worker.run_job", AsyncMock(return_value=JobOutcome("ok", {}))), patch("worker.push_text"):
        assert await worker.drain(_inbox([JOB, {**JOB, "id": 8}])) == 2


def test_done_retries_transient_errors():
    inbox = _inbox([], done_fail_times=2)
    assert inbox.done(7, True, {}, retries=3, backoff_s=0)["status"] == "done"


def test_done_gives_up_after_retries():
    with pytest.raises(httpx.HTTPStatusError):
        _inbox([], done_fail_times=5).done(7, True, {}, retries=2, backoff_s=0)


@pytest.mark.asyncio
async def test_unknown_platform_fails_job():
    with patch("worker.push_text"):
        status = await worker.handle_job({**JOB, "platform": "tiktok"}, _inbox([], done_status="queued"))
    assert status == "queued"


def test_httpx_request_urls_are_not_logged():
    """httpx INFO 會把 Discord webhook 網址（含 token）寫進 log"""
    import logging
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
