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

## Notes
- 零 API 成本方案：`claude --print`（走 Max 額度）+ `mlx-whisper`（本地 M1 加速）
- Task 3、4 spike 發現 IG/Threads 新版 JSON 結構（2025+），parser 已適配
- 共用 `PostData` dataclass 和 `_extract_image`/`_extract_video` helpers（DRY）
- 32 個單元測試全部通過
- 整合測試需要：關閉 Chrome、真實 Sheet、claude CLI Max 訂閱
