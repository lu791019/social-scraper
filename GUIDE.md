# Social Scraper — Developer Guide

## 專案概述

從 Google Sheet 讀取 IG/Threads 貼文連結，自動爬取內容（文字 + 圖片 OCR + 影片逐字稿），用 Claude 產摘要，寫回 Sheet。零 API 成本。

## 快速啟動

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝 Patchright 瀏覽器
uv run patchright install chromium

# 3. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 GOOGLE_SHEET_URL

# 4. 放入 Google Cloud credentials
# 將 Service Account JSON 金鑰存為 credentials.json

# 5. 執行（關閉 Chrome 後再跑）
uv run python main.py
```

## 專案結構

```
social-scraper/
├── main.py              # 主控流程 + CLI 入口
├── config.py            # 設定（環境變數、常數）
├── scraper/
│   ├── browser.py       # Patchright 瀏覽器管理 + 防封（UA/viewport 輪替）
│   ├── instagram.py     # IG 貼文/Reels 抓取（嵌入 JSON 解析）
│   └── threads.py       # Threads 貼文抓取（嵌入 JSON 解析）
├── media/
│   ├── ocr.py           # 圖片 OCR（claude --print --image）
│   └── transcriber.py   # 影片→ffmpeg→mlx-whisper 逐字稿
├── services/
│   ├── sheet.py         # Google Sheet 讀寫（gspread）
│   └── summarizer.py    # Claude 摘要（claude --print）
├── tests/
│   ├── fixtures/        # spike 取得的真實 JSON 結構
│   └── test_*.py        # 單元測試 + 整合測試
├── docs/plans/          # 設計文件 + 實作計劃
├── .env                 # 環境變數（不進版控）
├── credentials.json     # Google Service Account 金鑰（不進版控）
└── pyproject.toml       # 依賴管理（uv）
```

## 技術棧

| 元件 | 技術 | 說明 |
|------|------|------|
| 爬蟲 | Patchright (async) | Playwright fork，移除自動化痕跡 |
| OCR | `claude --print --image` | 走 Max 額度，零成本 |
| 摘要 | `claude --print` | 走 Max 額度，零成本 |
| STT | mlx-whisper | Apple Silicon 本地加速，零成本 |
| Sheet | gspread + Service Account | Google Sheets API |
| 音軌擷取 | ffmpeg | 影片→MP3 |

## Google Sheet 欄位

| 欄位 | 標題 | 內容 |
|------|------|------|
| A | 社群連結 | 使用者手動貼入 URL |
| B | 原始內容 | 【貼文文字】+【圖片文字】+【影片逐字稿】 |
| C | AI 摘要 | Claude 產出的 2-3 句摘要 |

## 測試方式

```bash
# 單元測試
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需要真實環境）
uv run pytest tests/test_integration.py -v -m integration -s
```

## 注意事項

- **Patchright 不能與 Chrome 共存**：執行前需先關閉所有 Chrome 程序
- **每日上限 30 篇**：硬編碼在 `config.py` 的 `DAILY_LIMIT`
- **mlx-whisper 首次下載**：第一次執行時自動下載模型 ~1.5GB
- **claude --print 輸出清理**：偶爾帶思考殘留，程式碼用 `.strip()` 處理

## 相關文件

- [PLAN.md](PLAN.md) — 設計決策與計劃索引
- [task.md](task.md) — 實作進度追蹤
- [implementation_plan.md](implementation_plan.md) — Session handoff 摘要
- [planning.md](planning.md) — 原始技術規劃（含防封策略詳細說明）
