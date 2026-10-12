#!/bin/bash
# Mac 工作程式（launchd: com.dex.social-scraper.worker）：向 Cloud Run 收件服務拉單處理
set -euo pipefail
cd "$(dirname "$0")/.."
echo "$(date '+%F %T') 啟動 worker"
exec uv run --frozen python worker.py
