# Social Scraper — PLAN

> 本文件為索引，完整內容見下方連結。

## 設計文件

- [`docs/plans/2026-02-19-social-scraper-design.md`](docs/plans/2026-02-19-social-scraper-design.md) — 架構、技術棧、防封策略、爬取邏輯、媒體處理、Google Sheet 欄位設計

## 實作計劃

- [`docs/plans/2026-02-19-social-scraper-implementation.md`](docs/plans/2026-02-19-social-scraper-implementation.md) — 10 個 task 的完整實作步驟（含程式碼、測試、commit 訊息）

## 核心決策

| 決策 | 選擇 | 理由 |
|------|------|------|
| 爬蟲方案 | Patchright（修補版 Playwright） | 反偵測最強、積極維護、IG/Threads 共用同一套 |
| LLM 摘要 + OCR | `claude --print`（Max 額度） | 零 API 成本 |
| 語音轉文字 | mlx-whisper（本地 M1 加速） | 零 API 成本、隱私 |
| Google Sheet | gspread + Service Account | A=連結、B=原始內容、C=AI 摘要 |
| 不登入 | 匿名瀏覽公開內容 | 零帳號封禁風險 |
| Trello | MVP 不做 | 之後再加 |
