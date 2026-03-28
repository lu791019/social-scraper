# Social Scraper

從 LINE 傳送連結，自動爬取內容並用 Claude 產摘要，寫回 Google Sheet。**零 API 成本**。

支援平台：
- **Instagram / Threads** — 貼文文字 + 圖片 OCR + 影片逐字稿 → 摘要 + 關鍵點
- **GitHub** — Repo 資訊 + README 中文翻譯/摘要 + 使用情境
- **一般網頁** — 全文擷取 → 存入 Notion Database（適合讀取慢的網站如數位時代）

## 架構流程

```
LINE 傳連結
  ├── IG/Threads URL → Patchright 爬取 → OCR/STT → 摘要 → Sheet1
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
- [ngrok](https://ngrok.com/) (LINE webhook 測試用)
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

### 方式一：LINE Bot（推薦）

```bash
# 1. 先關閉 Chrome（Patchright 限制，僅 IG/Threads 需要）
pkill -f "Google Chrome"

# 2. 啟動 webhook server
uv run uvicorn line_webhook.app:app --port 8000 &

# 3. 啟動 ngrok（另一個終端）
ngrok http 8000

# 4. 將 ngrok 產生的 HTTPS URL + /callback 設為 LINE Webhook URL
#    例：https://xxxx.ngrok-free.app/callback
#    到 LINE Developers Console → Messaging API → Webhook URL → Update
#    開啟 Use webhook

# 5. 在 LINE 傳連結給 Bot
#    - IG/Threads 連結 → 寫入 Sheet1
#    - GitHub repo 連結 → 寫入 GitHub 工作表
#    - 其他網頁連結 → 全文存入 Notion
```

> **注意：** ngrok 每次重啟會換 URL，需要重新到 LINE Developers Console 更新 Webhook URL。

### 方式二：手動批次處理

```bash
# 先在 Google Sheet 手動貼入 URL：
#   - IG/Threads URL → Sheet1 A 欄
#   - GitHub URL → GitHub 工作表 A 欄
# 然後：
pkill -f "Google Chrome"
uv run python main.py
```

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
├── main.py                      # 批次主控流程（IG/Threads + GitHub）
├── config.py                    # 設定（環境變數、常數）
├── line_webhook/
│   ├── app.py                   # FastAPI webhook server（LINE Bot）
│   └── line_handler.py          # URL 提取、平台驗證
├── scraper/
│   ├── browser.py               # Patchright 瀏覽器管理 + 防封
│   ├── instagram.py             # IG 貼文解析
│   ├── threads.py               # Threads 貼文解析
│   ├── github.py                # GitHub repo 資訊 + README 取得
│   └── article.py               # 一般網頁全文擷取（httpx + readability）
├── media/
│   ├── ocr.py                   # 圖片 OCR（claude --print）
│   └── transcriber.py           # 影片 → ffmpeg → mlx-whisper
├── services/
│   ├── sheet.py                 # Google Sheet 讀寫（Sheet1 + GitHub）
│   ├── summarizer.py            # IG/Threads 摘要 + 關鍵點
│   ├── github_summarizer.py     # GitHub README 中文摘要 + 使用情境
│   └── notion.py                # Notion Database 寫入（全文存檔）
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
| 網頁全文擷取 | httpx + readability-lxml | 免費 |
| Notion 存檔 | notion-client SDK | 免費 |
| OCR + 摘要 | `claude --print` (Max 額度) | 零 API 費 |
| 語音轉文字 | mlx-whisper (Apple Silicon) | 零 API 費 |
| LINE Bot | FastAPI + line-bot-sdk | 免費 |
| Sheet 存取 | gspread + Service Account | 免費 |
| 音軌擷取 | ffmpeg | 免費 |

## 測試

```bash
# 單元測試（72 個）
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需關閉 Chrome + 真實 Sheet + Claude Max）
uv run pytest tests/test_integration.py -v -m integration -s
```

## 佇列機制與進度查詢

- **併發限制**：同時最多處理 2 筆任務，其餘自動排隊
- **即時進度**：每筆任務開始處理、完成或失敗時，LINE 會主動推播狀態
- **主動查詢**：在 LINE 輸入「進度」、「狀態」或「status」即可查看目前佇列

## 注意事項

- **Patchright 不能與 Chrome 共存**：執行 IG/Threads 爬取前必須關閉所有 Chrome（GitHub 不受此限）
- **每日上限 30 篇**：`config.py` 的 `DAILY_LIMIT`
- **mlx-whisper 首次下載**：第一次執行自動下載模型 ~1.5GB
- **ngrok URL 會變**：每次重啟 ngrok 需更新 LINE Webhook URL
- **GitHub API 限額**：未設 token 為 60 req/hr，設了為 5000 req/hr
