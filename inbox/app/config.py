"""設定只從環境變數讀。機密由 Cloud Run 從 Secret Manager 注入：

- DATABASE_URL：沿用 channel-learn 的 secret `database-url`
- INBOX_SECRETS：secret `social-scraper-inbox`，JSON
  {"line_channel_secret": "...", "line_channel_access_token": "...", "worker_key": "..."}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    line_channel_secret: str
    line_channel_access_token: str
    worker_key: str
    max_attempts: int = 3
    lease_minutes: int = 30


def load_settings() -> Settings:
    secrets = json.loads(os.environ.get("INBOX_SECRETS", "{}") or "{}")
    settings = Settings(
        database_url=os.environ.get("DATABASE_URL", ""),
        line_channel_secret=secrets.get("line_channel_secret", ""),
        line_channel_access_token=secrets.get("line_channel_access_token", ""),
        worker_key=secrets.get("worker_key", ""),
        max_attempts=int(os.environ.get("MAX_ATTEMPTS", "3")),
        lease_minutes=int(os.environ.get("LEASE_MINUTES", "30")),
    )
    missing = [k for k in ("database_url", "line_channel_secret", "line_channel_access_token", "worker_key")
               if not getattr(settings, k)]
    if missing:
        raise RuntimeError(f"缺少設定：{', '.join(missing)}")
    return settings
