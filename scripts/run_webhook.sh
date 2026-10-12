#!/bin/bash
# LINE webhook server（launchd: com.dex.social-scraper）
# 埠由 .env 的 WEBHOOK_PORT 決定，預設 8010（8000 被 channel-learn 佔用）
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
PORT="${WEBHOOK_PORT:-8010}"
echo "$(date '+%F %T') 啟動 uvicorn 127.0.0.1:${PORT}"
exec uv run --frozen uvicorn line_webhook.app:app --host 127.0.0.1 --port "$PORT"
