"""scraper_jobs 佇列存取。

- claim：FOR UPDATE SKIP LOCKED，多個 worker 同時拉也只會有一個拿到同一筆
- 租約：working 超過 lease_minutes 沒回報（Mac 中途當機／睡眠）視為可重領；次數用完直接標 error
- done：只對 status='working' 生效 → 重送同一個結果是 no-op（冪等）
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

SCHEMA_SQL = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


@dataclass(frozen=True)
class Job:
    id: int
    url: str
    platform: str
    line_user_id: str | None
    status: str
    attempts: int
    result_json: dict | None
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        return {
            "id": self.id, "url": self.url, "platform": self.platform,
            "line_user_id": self.line_user_id, "status": self.status, "attempts": self.attempts,
            "result": self.result_json,
            "created_at": self.created_at.isoformat(), "updated_at": self.updated_at.isoformat(),
        }


def _job(row: dict | None) -> Job | None:
    return Job(**row) if row else None


class JobStore:
    def __init__(self, database_url: str, max_attempts: int = 3, lease_minutes: int = 30,
                 min_size: int = 0, max_size: int = 4):
        # Supabase pooler（transaction mode）不支援 prepared statement → prepare_threshold=None
        self._pool = ConnectionPool(
            database_url, min_size=min_size, max_size=max_size, open=True,
            kwargs={"prepare_threshold": None, "row_factory": dict_row, "autocommit": True},
        )
        self.max_attempts = max_attempts
        self.lease_minutes = lease_minutes

    def close(self) -> None:
        self._pool.close()

    def ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(SCHEMA_SQL)

    def enqueue(self, links: list[tuple[str, str]], line_user_id: str | None) -> list[Job]:
        jobs: list[Job] = []
        with self._pool.connection() as conn:
            with conn.transaction():
                for url, platform in links:
                    row = conn.execute(
                        "INSERT INTO scraper_jobs (url, platform, line_user_id) VALUES (%s, %s, %s) RETURNING *",
                        (url, platform, line_user_id),
                    ).fetchone()
                    jobs.append(_job(row))
        return jobs

    def pending_count(self) -> int:
        with self._pool.connection() as conn:
            row = conn.execute(
                "SELECT count(*) AS n FROM scraper_jobs WHERE status IN ('queued', 'working')"
            ).fetchone()
        return int(row["n"])

    def _expire_stale(self, conn) -> None:
        conn.execute(
            """
            UPDATE scraper_jobs
               SET status = 'error', updated_at = now(),
                   result_json = jsonb_build_object('error', '處理逾時且已達重試上限')
             WHERE status = 'working' AND attempts >= %(max)s
               AND updated_at < now() - make_interval(mins => %(lease)s)
            """,
            {"max": self.max_attempts, "lease": self.lease_minutes},
        )

    def claim(self) -> Job | None:
        with self._pool.connection() as conn:
            self._expire_stale(conn)
            row = conn.execute(
                """
                WITH picked AS (
                    SELECT id FROM scraper_jobs
                     WHERE status = 'queued'
                        OR (status = 'working' AND updated_at < now() - make_interval(mins => %(lease)s))
                     ORDER BY created_at, id
                     FOR UPDATE SKIP LOCKED
                     LIMIT 1
                )
                UPDATE scraper_jobs j
                   SET status = 'working', attempts = j.attempts + 1, updated_at = now()
                  FROM picked WHERE j.id = picked.id
                RETURNING j.*
                """,
                {"lease": self.lease_minutes},
            ).fetchone()
        return _job(row)

    def finish(self, job_id: int, success: bool, result: dict | None, error: str | None) -> tuple[Job | None, bool]:
        """回傳 (job, changed)。job 不存在回 (None, False)；已非 working 回 (現況, False)。"""
        payload = result if success else {**(result or {}), "error": error or "unknown error"}
        with self._pool.connection() as conn:
            row = conn.execute(
                """
                UPDATE scraper_jobs
                   SET status = CASE WHEN %(success)s THEN 'done'
                                     WHEN attempts >= %(max)s THEN 'error'
                                     ELSE 'queued' END,
                       result_json = %(payload)s, updated_at = now()
                 WHERE id = %(id)s AND status = 'working'
                RETURNING *
                """,
                {"success": success, "max": self.max_attempts, "payload": Jsonb(payload), "id": job_id},
            ).fetchone()
            if row:
                return _job(row), True
            current = conn.execute("SELECT * FROM scraper_jobs WHERE id = %s", (job_id,)).fetchone()
        return _job(current), False


