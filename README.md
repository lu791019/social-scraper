# Social Scraper

從 LINE 傳送 IG/Threads 貼文連結，自動爬取內容（文字 + 圖片 OCR + 影片逐字稿），用 Claude 產摘要與關鍵點，寫回 Google Sheet。**零 API 成本**。

## 架構流程

```
LINE 傳連結 → Bot 回覆「已收到」→ 寫入 Google Sheet
                                        ↓ (背景)
                              Patchright 爬取貼文
                                        ↓
                         圖片 OCR / 影片逐字稿 / 文字擷取
                                        ↓
                           claude --print 摘要 + 關鍵點
                                        ↓
                              寫回 Sheet → LINE 推播結果
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

# 3. 安裝 Patchright 瀏覽器
uv run patchright install chromium

# 4. 設定環境變數
cp .env.example .env
# 編輯 .env，填入以下值：
#   GOOGLE_SHEET_URL=你的 Google Sheet URL
#   LINE_CHANNEL_SECRET=你的 LINE Channel Secret
#   LINE_CHANNEL_ACCESS_TOKEN=你的 LINE Channel Access Token

# 5. 放入 Google Cloud credentials
# 將 Service Account JSON 金鑰存為 credentials.json（根目錄）

# 6. mlx-whisper 模型（首次執行時自動下載 ~1.5GB）
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
# 1. 先關閉 Chrome（Patchright 限制）
pkill -f "Google Chrome"

# 2. 啟動 webhook server
uv run uvicorn line_webhook.app:app --port 8000 &

# 3. 啟動 ngrok（另一個終端）
ngrok http 8000

# 4. 將 ngrok 產生的 HTTPS URL + /callback 設為 LINE Webhook URL
#    例：https://xxxx.ngrok-free.app/callback
#    到 LINE Developers Console → Messaging API → Webhook URL → Update
#    開啟 Use webhook

# 5. 在 LINE 傳 IG/Threads 連結給 Bot
```

> **注意：** ngrok 每次重啟會換 URL，需要重新到 LINE Developers Console 更新 Webhook URL。

### 方式二：手動批次處理

```bash
# 先在 Google Sheet A 欄手動貼入 URL，然後：
pkill -f "Google Chrome"
uv run python main.py
```

## 專案結構

```
social-scraper/
├── main.py                # 批次主控流程
├── config.py              # 設定（環境變數、常數）
├── line_webhook/
│   ├── app.py             # FastAPI webhook server（LINE Bot）
│   └── line_handler.py    # URL 提取、平台驗證
├── scraper/
│   ├── browser.py         # Patchright 瀏覽器管理 + 防封
│   ├── instagram.py       # IG 貼文解析（嵌入 JSON 遞迴搜尋）
│   └── threads.py         # Threads 貼文解析
├── media/
│   ├── ocr.py             # 圖片 OCR（claude --print）
│   └── transcriber.py     # 影片 → ffmpeg → mlx-whisper 逐字稿
├── services/
│   ├── sheet.py           # Google Sheet 讀寫（gspread）
│   └── summarizer.py      # Claude 摘要 + 關鍵點（單次呼叫）
├── tests/                 # 49 個單元測試 + 整合測試
├── .env.example           # 環境變數範例
├── credentials.json       # Google Service Account 金鑰（不進版控）
└── pyproject.toml         # 依賴管理（uv）
```

## 技術棧

| 元件 | 技術 | 成本 |
|------|------|------|
| 爬蟲 | Patchright (Playwright fork) | 免費 |
| OCR + 摘要 | `claude --print` (Max 額度) | 零 API 費 |
| 語音轉文字 | mlx-whisper (Apple Silicon) | 零 API 費 |
| LINE Bot | FastAPI + line-bot-sdk | 免費 |
| Sheet 存取 | gspread + Service Account | 免費 |
| 音軌擷取 | ffmpeg | 免費 |

## Google Sheet 欄位

| 欄 | 內容 |
|----|------|
| A | 社群連結（手動貼或 LINE Bot 自動寫入） |
| B | AI 摘要（2-3 句） |
| C | 關鍵點（3~5 個 bullet） |
| D | 執行日期 |

## 測試

```bash
# 單元測試（49 個）
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需關閉 Chrome + 真實 Sheet + Claude Max）
uv run pytest tests/test_integration.py -v -m integration -s
```

## 注意事項

- **Patchright 不能與 Chrome 共存**：執行前必須關閉所有 Chrome
- **每日上限 30 篇**：`config.py` 的 `DAILY_LIMIT`
- **mlx-whisper 首次下載**：第一次執行自動下載模型 ~1.5GB
- **ngrok URL 會變**：每次重啟 ngrok 需更新 LINE Webhook URL
