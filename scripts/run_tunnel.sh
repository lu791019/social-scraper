#!/bin/bash
# ngrok 通道（launchd: com.dex.social-scraper.tunnel）
# - .env 有 NGROK_DOMAIN（ngrok 免費靜態網域）→ 網址固定
# - 沒有 → 隨機網址；啟動後自動把 LINE webhook 同步到新網址
# ngrok 結束時本腳本跟著結束，交給 launchd KeepAlive 重啟
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; [ -f .env ] && source .env; set +a
PORT="${WEBHOOK_PORT:-8010}"
INSPECT="${NGROK_INSPECT_ADDR:-127.0.0.1:4040}"  # ngrok 預設 inspector；改埠需在 ngrok.yml 設 web_addr

args=(http "$PORT" --log stdout)
[ -n "${NGROK_DOMAIN:-}" ] && args+=(--url "https://${NGROK_DOMAIN}")

echo "$(date '+%F %T') 啟動 ngrok → localhost:${PORT}（domain: ${NGROK_DOMAIN:-隨機}）"
ngrok "${args[@]}" &
NGROK_PID=$!
trap 'kill $NGROK_PID 2>/dev/null' TERM INT

uv run --frozen python scripts/sync_line_webhook.py --inspect "$INSPECT" --port "$PORT" \
  || echo "$(date '+%F %T') ⚠️ LINE webhook 同步失敗（見上方訊息），ngrok 仍在跑"

wait $NGROK_PID
echo "$(date '+%F %T') ngrok 已結束（exit $?）"
