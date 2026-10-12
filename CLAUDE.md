# social-scraper 專案規則與踩坑

## 架構（拆兩半）
- LINE webhook → Cloud Run `social-scraper-inbox`（`inbox/`，GCP 用 `CLOUDSDK_ACTIVE_CONFIG_NAME=channel-learn`，asia-east1，min-instances 0）→ Supabase `scraper_jobs`
- Mac 只跑 `worker.py`（launchd `com.dex.social-scraper.worker`）向收件服務拉單；**Mac 連不到 Supabase pooler**，不要讓 Mac 直連 DB
- `scraper_jobs` 由收件服務啟動時冪等建立（`inbox/app/schema.sql`），不放進 channel-learn 的 migrations 編號；public schema 一定要開 RLS
- 機密：`social-scraper-inbox` 是一個 JSON secret（LINE secret／token、worker_key），刻意合併成一個以壓 Secret Manager 版本數；本機對應 `.env` 的 `INBOX_WORKER_KEY`
- 收件服務測試用拋棄式 postgres 容器（`inbox/tests/conftest.py`），不要連其他專案的 DB 容器
- worker 的 Sheet 寫入放在處理成功之後，重試才不會重複列；done 只改 working 狀態（冪等）
- httpx 的 INFO log 會印出完整網址（含 Discord webhook token）：worker／app／main 都把 httpx logger 壓到 WARNING，新程式也要照做

## 執行環境（備援模式）
- 本機 webhook 埠是 **8010**（`WEBHOOK_PORT`）。8000 被 channel-learn API 佔用，不要改回 8000
- 備援 plist（`com.dex.social-scraper`、`com.dex.social-scraper.tunnel`）在 `deploy/`，目前**未安裝**；啟用 tunnel 會把 LINE webhook 改到 ngrok，恢復雲端要跑 `scripts/sync_line_webhook.py --url <Cloud Run>`
- 備援與 worker 不可同時跑（都會處理 IG/Threads）
- launchd PATH 很窄：plist 已補 `/opt/homebrew/bin` 與 `~/.local/bin`。`which claude` 在 cmux 終端會指到 cmux wrapper，launchd 用的是 `~/.local/bin/claude`
- `.venv` 不存在或 patchright 升級後，要 `uv sync` + `uv run patchright install chromium`，否則爬蟲報 Executable doesn't exist

## LINE / ngrok（備援）
- ngrok 帳號目前沒有靜態網域：每次重啟換網址，`scripts/run_tunnel.sh` 會自動 PUT 到 LINE 並跑 webhook test。領到靜態網域後填 `.env` 的 `NGROK_DOMAIN`
- ngrok v3 沒有 `--web-addr` 旗標，inspector 固定用 ngrok.yml 的 `web_addr`（預設 127.0.0.1:4040）
- LINE token 只放在 header；任何 log、錯誤訊息、回報都不能印出 token 或 Discord webhook URL

## 爬蟲
- 不需要關使用者的 Chrome：Patchright 用自帶 headless Chromium（獨立 profile）。不要寫 `pkill Chrome`
- Threads 2026 版面：目標貼文在 `__bbox.result.data.media`，`thread_items` 是其他推薦串。一律用網址短碼比對 `code` 欄位（`scraper/page_json.find_post_by_code`），不要取 `thread_items[0]`
- 頁面 JSON 偶爾晚於 networkidle 才出現，Threads 會重讀 4 次
- 教室／公司網路的 FortiGate 會攔截 instagram.com 與 cdninstagram.com（憑證 issuer 是 Fortinet，回應是 Application Blocked 頁）。這不是程式 bug；IG 實測要換網路
- 媒體（OCR／轉錄）失敗會降級成只用貼文文字，但警告必須帶到 LINE 訊息，不可靜默

## Discord 出口
- 只有 IG/Threads 發 Discord；GitHub、一般網頁先不發
- 點評與標題來自摘要 prompt 的 `【Discord標題】`、`【Discord點評】` 段落；`_parse_summary_and_key_points` 會把它們切掉，Sheet 欄位內容不可被污染
- Discord 失敗只記 log 回 False，不拋例外；測試一律 mock httpx，真發只在端到端驗證時做
