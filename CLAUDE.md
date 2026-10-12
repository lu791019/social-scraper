# social-scraper 專案規則與踩坑

## 執行環境
- webhook 埠是 **8010**（`WEBHOOK_PORT`）。8000 被 channel-learn API 佔用，不要改回 8000
- 服務由 launchd 常駐：`com.dex.social-scraper`（uvicorn）、`com.dex.social-scraper.tunnel`（ngrok）。plist 原檔在 `deploy/`，改完要複製到 `~/Library/LaunchAgents/` 再 unload/load
- 改程式碼後 `launchctl kickstart -k gui/$(id -u)/com.dex.social-scraper`；不要另外手動起 uvicorn 搶 8010
- launchd PATH 很窄：plist 已補 `/opt/homebrew/bin` 與 `~/.local/bin`。`which claude` 在 cmux 終端會指到 cmux wrapper，launchd 用的是 `~/.local/bin/claude`
- `.venv` 不存在或 patchright 升級後，要 `uv sync` + `uv run patchright install chromium`，否則爬蟲報 Executable doesn't exist

## LINE / ngrok
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
