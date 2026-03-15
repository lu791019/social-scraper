# Social Scraper — Developer Guide

## 專案概述

從 LINE 傳送 IG/Threads 貼文連結，自動爬取內容（文字 + 圖片 OCR + 影片逐字稿），用 Claude 產摘要與關鍵點，寫回 Google Sheet。零 API 成本。

## 快速啟動

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝 Patchright 瀏覽器
uv run patchright install chromium

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 GOOGLE_SHEET_URL、LINE_CHANNEL_SECRET、LINE_CHANNEL_ACCESS_TOKEN

# 4. 放入 Google Cloud credentials
# 將 Service Account JSON 金鑰存為 credentials.json

# 5. LINE Bot 模式（關閉 Chrome 後）
uv run uvicorn line_webhook.app:app --port 8000 &
ngrok http 8000
# 將 ngrok URL + /callback 設為 LINE Webhook URL

# 6. 或批次模式
uv run python main.py
```

## 專案結構

```
social-scraper/
├── main.py                # 批次主控流程 + CLI 入口
├── config.py              # 設定（環境變數、常數）
├── line_webhook/
│   ├── app.py             # FastAPI webhook server（LINE Bot 入口）
│   └── line_handler.py    # URL 提取、平台驗證
├── scraper/
│   ├── browser.py         # Patchright 瀏覽器管理 + 防封（UA/viewport 輪替）
│   ├── instagram.py       # IG 貼文/Reels 抓取（嵌入 JSON 遞迴解析）
│   └── threads.py         # Threads 貼文抓取（嵌入 JSON 遞迴解析）
├── media/
│   ├── ocr.py             # 圖片 OCR（claude --print，支援批次）
│   └── transcriber.py     # 影片→ffmpeg→mlx-whisper 逐字稿
├── services/
│   ├── sheet.py           # Google Sheet 讀寫 + append_url（gspread）
│   └── summarizer.py      # Claude 摘要+關鍵點（單次呼叫優化）
├── tests/                 # 49 個單元測試 + 整合測試
├── docs/plans/            # 設計文件 + 實作計劃
├── .env                   # 環境變數（不進版控）
├── credentials.json       # Google Service Account 金鑰（不進版控）
└── pyproject.toml         # 依賴管理（uv）
```

## 技術棧

| 元件 | 技術 | 說明 |
|------|------|------|
| 爬蟲 | Patchright (async) | Playwright fork，移除自動化痕跡 |
| OCR | `claude --print` | 走 Max 額度，零成本，支援批次多張圖 |
| 摘要+關鍵點 | `claude --print` | 單次呼叫同時產出摘要和關鍵點 |
| STT | mlx-whisper | Apple Silicon 本地加速，零成本 |
| LINE Bot | FastAPI + line-bot-sdk v3 | Webhook 接收訊息，背景觸發 scraper |
| Sheet | gspread + Service Account | Google Sheets API |
| 音軌擷取 | ffmpeg | 影片→MP3 |

## Google Sheet 欄位

| 欄 | 內容 |
|----|------|
| A | 社群連結（手動貼或 LINE Bot 自動寫入） |
| B | AI 摘要（2-3 句） |
| C | 關鍵點（3~5 個 bullet） |
| D | 執行日期 |

## 測試方式

```bash
# 單元測試（49 個）
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需要真實環境）
uv run pytest tests/test_integration.py -v -m integration -s
```

## 注意事項

- **Patchright 不能與 Chrome 共存**：執行前需先關閉所有 Chrome 程序
- **每日上限 30 篇**：硬編碼在 `config.py` 的 `DAILY_LIMIT`
- **mlx-whisper 首次下載**：第一次執行時自動下載模型 ~1.5GB
- **ngrok URL 會變**：每次重啟需更新 LINE Webhook URL

## 相關文件

- [PLAN.md](PLAN.md) — 設計決策與計劃索引
- [task.md](task.md) — 實作進度追蹤
- [implementation_plan.md](implementation_plan.md) — 最新功能實作計劃
- [planning.md](planning.md) — 原始技術規劃（含防封策略詳細說明）
