# Social Scraper — Task Tracker

> **Plan**: `docs/plans/2026-02-19-social-scraper-implementation.md`
> **Design**: `docs/plans/2026-02-19-social-scraper-design.md`
> **Branch**: `feat/social-scraper`

## 前置條件 (完成)
- [x] ffmpeg 安裝 (v8.0.1) → `已確認`
- [x] Google Cloud Service Account + credentials.json → `已就位`
- [x] Google Sheet 建立並共享給 Service Account → `已完成`
- [x] .env 建立（GOOGLE_SHEET_URL） → `已完成`
- [x] Feature branch 建立 → `ea4845b`
- [x] Patchright 瀏覽器安裝 → `已完成`
- [ ] mlx-whisper 模型首次下載（首次執行 `process_video` 時自動下載，~1.5GB）

## Section A: 基礎建設 (完成)
- [x] Task 1: 專案骨架與依賴 → `cc1d408`
- [x] Task 2: 瀏覽器管理模組 → `cc1d408`

## Section B: 爬蟲核心 (完成)
- [x] Task 3: Instagram 爬蟲（含 spike） → `d7ea6ec`
  - Spike 發現：IG 新版 JSON 用 `xdt_api__v1__media__shortcode__web_info`
- [x] Task 4: Threads 爬蟲（含 spike） → `d7ea6ec`
  - Spike 發現：Threads JSON 在 `thread_items[].post` 中

## Section C: 媒體處理 (完成)
- [x] Task 5: 圖片 OCR（claude --print） → `5837e09`
- [x] Task 6: 影片逐字稿（ffmpeg + mlx-whisper） → `5837e09`

## Section D: 服務整合 (完成)
- [x] Task 7: Google Sheet 讀寫 → `c65bef9`
- [x] Task 8: LLM 摘要（claude --print） → `c65bef9`

## Section E: 整合 (完成)
- [x] Task 9: 主控流程 → `c305cfc`
- [x] Task 10: 端對端整合測試 → `c305cfc`

## Section F: LLM 呼叫優化 (完成)
- [x] Task 11: 合併 summarize + key_points 為單次呼叫 → `88235ef`
- [x] Task 12: 批次 OCR（多張圖合併一次 claude --print） → `88235ef`

## Section G: LINE Bot 整合 (完成)
- [x] Task 13: LINE Bot 前置設定（LINE Developers Console、環境變數）
- [x] Task 14: LINE webhook server（FastAPI + line-bot-sdk）
- [x] Task 15: 訊息處理邏輯（URL 提取、平台驗證、寫入 Sheet）
- [x] Task 16: 單元測試 + 手動驗證

## Section H: GitHub 爬取 (完成)
- [x] Task 17: GitHub repo 爬取寫入 Google Sheet

## Section I: 任務佇列 (完成)
- [x] Task 18: Semaphore 佇列機制 + LINE 進度查詢

## Section J: 網頁全文擷取 → Notion (完成)
- [x] Task 19: 新增 readability-lxml + notion-client 依賴 → `8ed956f`
- [x] Task 20: config.py 新增 Notion 環境變數 → `266e064`
- [x] Task 21: scraper/article.py URL 清理 + metadata 提取 → `87c67a5`
- [x] Task 22: scraper/article.py 全文擷取 scrape_article → `70b5649`
- [x] Task 23: services/notion.py Notion 寫入 → `3e3d304`
- [x] Task 24: line_handler.py 新增 extract_general_urls → `7f31fc6`
- [x] Task 25: app.py 整合 article-to-Notion 流程 → `ba18154`
- [x] Task 26: 端對端整合測試（bnext → Notion）通過

## Notes
- 零 API 成本方案：`claude --print`（走 Max 額度）+ `mlx-whisper`（本地 M1 加速）
- Task 3、4 spike 發現 IG/Threads 新版 JSON 結構（2025+），parser 已適配
- 共用 `PostData` dataclass 和 `_extract_image`/`_extract_video` helpers（DRY）
- 38 個新增單元測試（article + notion + line_handler）全部通過
- 整合測試需要：關閉 Chrome、真實 Sheet、claude CLI Max 訂閱
