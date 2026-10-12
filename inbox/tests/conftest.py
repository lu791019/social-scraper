"""測試用拋棄式 Postgres：預設 docker 起 postgres:16-alpine（隨機埠），或用 INBOX_TEST_DATABASE_URL。"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid

import psycopg
import pytest

from app.db import JobStore

IMAGE = "postgres:16-alpine"


def _wait_ready(url: str, timeout_s: float = 30) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            with psycopg.connect(url, connect_timeout=2):
                return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


@pytest.fixture(scope="session")
def database_url():
    if url := os.environ.get("INBOX_TEST_DATABASE_URL"):
        yield url
        return
    if not shutil.which("docker"):
        pytest.skip("需要 docker 或 INBOX_TEST_DATABASE_URL")
    name = f"inbox-test-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        ["docker", "run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=test",
         "-p", "127.0.0.1::5432", IMAGE], check=True, capture_output=True,
    )
    try:
        port = subprocess.run(["docker", "port", name, "5432"], check=True, capture_output=True, text=True
                              ).stdout.strip().splitlines()[0].rsplit(":", 1)[1]
        url = f"postgresql://postgres:test@127.0.0.1:{port}/postgres"
        _wait_ready(url)
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


@pytest.fixture
def store(database_url):
    s = JobStore(database_url, max_attempts=3, lease_minutes=30, max_size=10)
    s.ensure_schema()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE scraper_jobs RESTART IDENTITY")
    yield s
    s.close()
