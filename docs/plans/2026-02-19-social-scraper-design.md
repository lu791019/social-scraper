# Social Scraper — 設計文件

> 日期：2026-02-19
> 狀態：已確認

## 目標

從 Google Sheet 讀取 Instagram / Threads 貼文連結，自動爬取內容（文字、圖片 OCR、影片逐字稿），用 Claude API 產出摘要，寫回 Google Sheet。

---

## 需求規格

| 項目 | 規格 |
|------|------|
| 爬取範圍 | 單篇貼文 URL（IG 貼文 / IG Reels / Threads） |
| 爬取內容 | 貼文文字 + 圖片 OCR + 影片/Reels 語音逐字稿（不含留言） |
| 使用頻率 | 每天 < 20 篇 |
| 輸入 | Google Sheet A 欄（社群連結） |
| 輸出 | B 欄（原始內容）、C 欄（AI 摘要） |
| Trello 整合 | MVP 不做，之後再加 |

---

## 架構

```
┌─────────────────────────┐
│     Google Sheet         │
│  A: 社群連結              │── gspread 讀取未處理的 URL
│  B: 原始內容              │◄─ 寫入（文字 + OCR + 逐字稿）
│  C: AI 摘要              │◄─ 寫入摘要
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│      Orchestrator        │  主控腳本
│  1. 讀取 Sheet 新 URL     │
│  2. 判斷平台（IG/Threads） │
│  3. Patchright 爬取       │
│  4. 媒體處理管線          │
│  5. Claude 摘要           │
│  6. 寫回 Sheet            │
└─────────────────────────┘
            │
     ┌──────┴──────┐
     ▼              ▼
┌─────────┐  ┌──────────┐
│IG       │  │ Threads  │   Patchright 開頁面
│Scraper  │  │ Scraper  │   提取嵌入 JSON
└─────────┘  └──────────┘
            │
            ▼
┌─────────────────────────┐
│     媒體處理管線          │
│  圖片 → Claude Vision OCR │
│  影片 → ffmpeg → Whisper  │
└─────────────────────────┘
            │
            ▼
┌─────────────────────────┐
│     Claude API 摘要      │
└─────────────────────────┘
```

---

## 技術棧

| 元件 | 選擇 | 理由 |
|------|------|------|
| 語言 | Python 3.12+ | gspread 生態成熟、Patchright 有 Python binding |
| 瀏覽器 | Patchright (async) | 反偵測最強的 Playwright fork，積極維護 |
| Sheet 讀寫 | gspread + Service Account | 官方推薦方式 |
| LLM 摘要 | Claude API (Sonnet) | 摘要任務不需 Opus，Sonnet 更快更便宜 |
| 圖片 OCR | Claude Vision (Sonnet) | 已用 Claude API，不增加依賴 |
| 語音轉文字 | OpenAI Whisper API | 最成熟 STT 服務，中文好，$0.006/min |
| 音軌擷取 | ffmpeg | 標準工具 |
| 套件管理 | uv | 快速、現代 |

---

## 防封策略

### 瀏覽器指紋層

| 策略 | 做法 |
|------|------|
| Patchright 內建 | 移除 `Runtime.enable`、`--enable-automation` 等自動化痕跡 |
| User-Agent 輪替 | 5-10 個真實 UA 池，每次 session 隨機選 |
| Viewport 隨機化 | 常見解析度隨機（1366x768、1440x900、1920x1080） |
| 語系 / 時區 | `zh-TW` / `Asia/Taipei` |

### 行為層

| 策略 | 做法 |
|------|------|
| 請求間隔 | 每篇之間隨機 3-8 秒 |
| 頁面互動 | 載入後隨機滾動 1-3 次，停留 2-5 秒 |
| 每日上限 | 硬上限 30 篇/天 |
| 不登入 | 全程匿名瀏覽公開內容 |

### IP 層

| 情境 | 策略 |
|------|------|
| MVP | 直接用本機 IP，低頻被封機率極低 |
| 被封時 | 加入住宅代理，程式碼預留 `proxy` 參數 |

### 不做的項目

- Canvas / WebGL 指紋偽裝（低頻不需要）
- 多帳號輪替（不登入）
- Cookie 管理（不登入）

---

## 爬取邏輯

### URL 路由

- `instagram.com` → IG Scraper
- `threads.net` → Threads Scraper

### IG 貼文 / Reels

1. Patchright 開貼文頁面
2. 從 `<script type="application/json">` 提取嵌入 JSON
3. 解析出：caption、圖片 URL 列表、影片 URL
4. 嵌入 JSON 前幾則熱門留言不抓

### Threads 貼文

1. Patchright 開貼文頁面（Threads 必須 JS 渲染）
2. 從 `<script type="application/json" data-sjs>` 提取嵌入 JSON
3. 解析出：caption、圖片 URL 列表、影片 URL

### 錯誤處理

| 情境 | 處理 |
|------|------|
| 頁面載入逾時 | 重試 1 次，仍失敗 → B 欄標記 `[ERROR] 載入逾時` |
| 登入牆彈出 | 偵測到登入表單 → `[ERROR] 需要登入` |
| JSON 解析失敗 | `[ERROR] 解析失敗`，log 記錄 HTML |
| IP 被封 | `[ERROR] 被封鎖` |

錯誤不中斷流程，標記後繼續下一列。

---

## 媒體處理管線

### 圖片 → OCR

- 用 Claude Vision (Sonnet) 傳圖片 URL
- Prompt：擷取圖片上所有文字，保持原始排版
- 無文字時回傳空字串，不寫入 B 欄

### 影片 / Reels → 逐字稿

1. `httpx` 下載影片到暫存檔
2. `ffmpeg` 抽取音軌為 MP3
3. OpenAI Whisper API 轉逐字稿（language=zh）
4. 清理暫存檔

---

## Google Sheet 欄位

| 欄位 | 標題 | 內容 |
|------|------|------|
| A | 社群連結 | 使用者手動貼入 URL |
| B | 原始內容 | 貼文文字 + 圖片 OCR + 影片逐字稿，用標記分段 |
| C | AI 摘要 | Claude 產出的摘要 |

### B 欄格式

```
【貼文文字】
（caption 內容）

【圖片文字】
（OCR 結果，無文字時省略此段）

【影片逐字稿】
（Whisper 結果，無影片時省略此段）
```

### 處理邏輯

- 掃描 A 欄有值但 C 欄為空的列
- 處理完成後同時寫入 B 欄和 C 欄

---

## 專案結構

```
social-scraper/
├── main.py              # 主控流程 + CLI 入口
├── scraper/
│   ├── __init__.py
│   ├── browser.py       # Patchright 瀏覽器管理 + 防封設定
│   ├── instagram.py     # IG 貼文/Reels 抓取
│   └── threads.py       # Threads 貼文抓取
├── media/
│   ├── __init__.py
│   ├── ocr.py           # Claude Vision OCR
│   └── transcriber.py   # 影片下載 + ffmpeg + Whisper
├── services/
│   ├── __init__.py
│   ├── sheet.py         # Google Sheet 讀寫
│   └── summarizer.py    # Claude API 摘要
├── config.py            # 設定（Sheet URL、API key 等）
├── .env                 # 環境變數（不進版控）
├── pyproject.toml       # 依賴管理
└── planning.md          # 原始規劃
```

---

## 執行方式

| 方式 | 說明 |
|------|------|
| 手動 | `python main.py` — 跑一次，處理所有待處理列 |
| 定時（選配） | cron 每小時跑一次 |

---

## 成本估算（每天 20 篇）

| 項目 | 月費估算 |
|------|----------|
| Claude API（摘要 + OCR） | ~$5-15 |
| Whisper API（語音轉文字） | ~$1-5 |
| 住宅代理（如需要） | $10-30 |
| **合計** | **$6-50/月** |
