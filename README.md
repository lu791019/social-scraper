# Social Scraper

從 LINE 傳送連結，自動爬取內容並用 Claude 產摘要，寫回 Google Sheet；IG/Threads 同時以「蛇摸影評」發到 Discord。**零 API 成本**。

支援平台：
- **Instagram / Threads** — 貼文文字 + 圖片 OCR + 影片逐字稿 → 摘要 + 關鍵點
- **GitHub** — Repo 資訊 + README 中文翻譯/摘要 + 使用情境
- **一般網頁** — 全文擷取 → Markdown 結構化排版存入 Notion Database（標題/清單/引用/連結）

## 架構流程

```
LINE 傳連結
  ├── IG/Threads URL → Patchright 爬取 → OCR/STT → 摘要 → Sheet1 + Discord（蛇摸影評）
  ├── GitHub URL → REST API → README 摘要 → "GitHub" worksheet
  └── 其他 URL → httpx + readability → 全文擷取 → Notion Database
                                    ↓
                           claude --print（走 Max 額度）
                                    ↓
                          寫回 Sheet / Notion → LINE 推播結果
```

## 前置需求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python 套件管理)
- ffmpeg (`brew install ffmpeg`)
- [ngrok](https://ngrok.com/)（`brew install ngrok`，並 `ngrok config add-authtoken <token>` 登入）
- Apple Silicon Mac (mlx-whisper 需要)
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-cli) 已登入 Max 訂閱

## 首次安裝

```bash
# 1. Clone
git clone https://github.com/lu791019/social-scraper.git
cd social-scraper

# 2. 安裝 Python 依賴
uv sync

# 3. 安裝 Patchright 瀏覽器（IG/Threads 用，GitHub 不需要）
uv run patchright install chromium

# 4. 設定環境變數
cp .env.example .env
# 編輯 .env，填入：
#   GOOGLE_SHEET_URL=你的 Google Sheet URL
#   LINE_CHANNEL_SECRET=你的 LINE Channel Secret
#   LINE_CHANNEL_ACCESS_TOKEN=你的 LINE Channel Access Token
#   GITHUB_TOKEN=（可選，提升 API 限額）
#   NOTION_TOKEN=你的 Notion Integration Token
#   NOTION_DATABASE_ID=你的 Notion Database ID

# 5. 放入 Google Cloud credentials
# 將 Service Account JSON 金鑰存為 credentials.json（根目錄）
```

### Google Cloud 設定

1. 建立 Service Account，下載 JSON 金鑰存為 `credentials.json`
2. 在 Google Sheet 中，將 Sheet 共享給 Service Account 的 email

### LINE Bot 設定

1. 到 [LINE Developers Console](https://developers.line.biz/) 建立 Messaging API Channel
2. 取得 **Channel Secret**（Basic settings 分頁）和 **Channel Access Token**（Messaging API 分頁 → Issue）
3. 在 [LINE Official Account Manager](https://manager.line.biz/) 關閉「自動回應訊息」
4. Webhook URL 在啟動 ngrok 後設定（見下方）

## 使用方式

### 方式一：LINE Bot（推薦，launchd 常駐）

兩個 LaunchAgent，登入後自動啟動、掛掉 30 秒內重啟：

| Label | 腳本 | 內容 | Log |
|-------|------|------|-----|
| `com.dex.social-scraper` | `scripts/run_webhook.sh` | uvicorn `127.0.0.1:${WEBHOOK_PORT:-8010}` | `logs/webhook.log`、`logs/webhook.err.log` |
| `com.dex.social-scraper.tunnel` | `scripts/run_tunnel.sh` | ngrok → 8010，啟動後自動同步 LINE webhook | `logs/tunnel.log`、`logs/tunnel.err.log` |

> 埠用 **8010**：8000 被 channel-learn API 佔用。要改就在 `.env` 設 `WEBHOOK_PORT`。

```bash
# 安裝 / 重新安裝
cp deploy/com.dex.social-scraper*.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.dex.social-scraper.plist
launchctl load ~/Library/LaunchAgents/com.dex.social-scraper.tunnel.plist

# 健康檢查
curl -s localhost:8010/health        # {"status":"ok","running":0,"waiting":0}

# 改了程式碼後重啟
launchctl kickstart -k gui/$(id -u)/com.dex.social-scraper

# 停用
launchctl unload ~/Library/LaunchAgents/com.dex.social-scraper.plist
launchctl unload ~/Library/LaunchAgents/com.dex.social-scraper.tunnel.plist
```

**固定網址（建議）**：ngrok 免費帳號可領 1 個靜態網域。

1. 登入 [dashboard.ngrok.com](https://dashboard.ngrok.com/) → 左側 **Universal Gateway → Domains**（舊版介面叫 Cloud Edge → Domains）
2. 按 **New Domain / Create Domain**，免費方案會配一個 `xxx.ngrok-free.app`
3. 寫進 `.env`：`NGROK_DOMAIN=xxx.ngrok-free.app`（不含 `https://`）
4. `launchctl kickstart -k gui/$(id -u)/com.dex.social-scraper.tunnel`

沒設 `NGROK_DOMAIN` 也能用：每次 ngrok 重啟換網址時，`run_tunnel.sh` 會呼叫 `scripts/sync_line_webhook.py`，把 LINE webhook 改成新網址並跑 LINE 的 webhook 測試，結果寫在 `logs/tunnel.log`。手動同步：

```bash
uv run python scripts/sync_line_webhook.py   # 需 ngrok 已在跑
```

在 LINE 傳連結給 Bot：
- IG/Threads 連結 → 寫入 Sheet1，並發 Discord
- GitHub repo 連結 → 寫入 GitHub 工作表
- 其他網頁連結 → 全文存入 Notion

### 方式二：手動批次處理

```bash
# 先在 Google Sheet 手動貼入 URL：
#   - IG/Threads URL → Sheet1 A 欄
#   - GitHub URL → GitHub 工作表 A 欄
# 然後：
uv run python main.py
```

## Discord 出口（IG/Threads）

`.env` 設 `DISCORD_WEBHOOK_URL`（與 `DISCORD_SNAKE_AVATAR`）後，IG/Threads 處理完成會在寫 Sheet 之後發一則 embed：

- 發文身分：username「蛇摸影評」、頭像 `DISCORD_SNAKE_AVATAR`
- embed：標題、原文連結、蛇摸點評（「嘶～」開頭的 1–2 句）、摘要、3–5 個重點、平台／作者、第一張圖
- 標題與點評由同一次 `claude --print` 產出（`【Discord標題】`、`【Discord點評】` 段落），不會寫進 Sheet
- 發送失敗只記 log，Sheet 與 LINE 照常；LINE 完成訊息會附「⚠️ Discord 未送出」
- GitHub 與一般網頁目前不發 Discord

## Google Sheet 欄位

### Sheet1（IG/Threads）

| 欄 | 內容 |
|----|------|
| A | 社群連結 |
| B | AI 摘要（2-3 句） |
| C | 關鍵點（3~5 個 bullet） |
| D | 執行日期 |

### GitHub 工作表（自動建立）

| 欄 | 內容 |
|----|------|
| A | Repo URL |
| B | Repo 名稱（owner/repo） |
| C | 官方說明 |
| D | README 中文摘要（5~10 句） |
| E | 使用情境（3~5 個 bullet） |
| F | 星數/語言 |
| G | 日期 |

## 專案結構

```
social-scraper/
├── main.py                      # 批次主控流程 + process_post_detailed（IG/Threads 共用）
├── scripts/
│   ├── run_webhook.sh           # launchd 用：啟動 uvicorn
│   ├── run_tunnel.sh            # launchd 用：啟動 ngrok + 同步 LINE webhook
│   └── sync_line_webhook.py     # 把 LINE webhook 指到目前 ngrok 網址並測試
├── deploy/                      # launchd plist（複製到 ~/Library/LaunchAgents）
├── config.py                    # 設定（環境變數、常數）
├── line_webhook/
│   ├── app.py                   # FastAPI webhook server（LINE Bot）
│   ├── line_handler.py          # URL 提取、平台驗證
│   └── endpoint_sync.py         # LINE webhook endpoint 讀取／設定／測試
├── scraper/
│   ├── browser.py               # Patchright 瀏覽器管理 + 防封
│   ├── instagram.py             # IG 貼文解析
│   ├── threads.py               # Threads 貼文解析
│   ├── github.py                # GitHub repo 資訊 + README 取得
│   ├── page_json.py             # 頁面內嵌 JSON：用網址短碼比對目標貼文
│   └── article.py               # 一般網頁全文擷取（httpx + readability）
├── media/
│   ├── ocr.py                   # 圖片 OCR（claude --print）
│   └── transcriber.py           # 影片 → ffmpeg → mlx-whisper
├── services/
│   ├── sheet.py                 # Google Sheet 讀寫（Sheet1 + GitHub）
│   ├── summarizer.py            # IG/Threads 摘要 + 關鍵點
│   ├── github_summarizer.py     # GitHub README 中文摘要 + 使用情境
│   ├── notion.py                # Notion Database 寫入（全文存檔）
│   └── discord_sink.py          # Discord webhook embed（蛇摸影評）
├── tests/                       # 單元測試 + 整合測試
├── .env.example                 # 環境變數範例
├── credentials.json             # Google Service Account 金鑰（不進版控）
└── pyproject.toml               # 依賴管理（uv）
```

## 技術棧

| 元件 | 技術 | 成本 |
|------|------|------|
| IG/Threads 爬蟲 | Patchright (Playwright fork) | 免費 |
| GitHub 爬取 | httpx + GitHub REST API | 免費 |
| 網頁全文擷取 | httpx + readability-lxml + markdownify | 免費 |
| Notion 存檔 | notion-client SDK（Markdown → Notion blocks） | 免費 |
| OCR + 摘要 | `claude --print` (Max 額度) | 零 API 費 |
| 語音轉文字 | mlx-whisper (Apple Silicon) | 零 API 費 |
| LINE Bot | FastAPI + line-bot-sdk | 免費 |
| Sheet 存取 | gspread + Service Account | 免費 |
| 音軌擷取 | ffmpeg | 免費 |

## 測試

```bash
# 單元測試（141 個）
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需真實 Sheet + Claude Max；不必關 Chrome）
uv run pytest tests/test_integration.py -v -m integration -s
```

## 佇列機制與進度查詢

- **併發限制**：同時最多處理 2 筆任務，其餘自動排隊
- **即時進度**：每筆任務開始處理、完成或失敗時，LINE 會主動推播狀態
- **主動查詢**：在 LINE 輸入「進度」、「狀態」或「status」即可查看目前佇列

## 注意事項

- **不必關 Chrome**：爬蟲用 Patchright 自帶的 headless Chromium（獨立 profile），可與使用者開著的 Chrome 共存。`uv sync` 後若升級了 patchright，要再跑 `uv run patchright install chromium`
- **防火牆封鎖 Instagram**：部分公司／教室網路（FortiGate）會攔截 instagram.com 與 cdninstagram.com 的 SSL。IG 貼文會失敗並提示換網路；Threads 文字照常，但圖片 OCR 會降級成只用貼文文字，LINE 訊息會標示警告
- **媒體降級不靜默**：圖片 OCR／影片轉錄失敗時以貼文文字繼續，警告會附在 LINE 完成訊息
- **每日上限 30 篇**：`config.py` 的 `DAILY_LIMIT`
- **mlx-whisper 首次下載**：第一次執行自動下載模型 ~1.5GB
- **ngrok URL 會變**：沒設 `NGROK_DOMAIN` 時由 `run_tunnel.sh` 自動同步 LINE webhook；設了靜態網域就固定
- **GitHub API 限額**：未設 token 為 60 req/hr，設了為 5000 req/hr
