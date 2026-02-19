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
- [ ] Patchright 瀏覽器安裝（`uv run patchright install chromium`）
- [ ] mlx-whisper 模型首次下載（Task 6 時自動下載，~1.5GB）

## Section A: 基礎建設 (待做)
- [ ] Task 1: 專案骨架與依賴
  - Create: `pyproject.toml`, `config.py`, `.env.example`
  - Modify: `.gitignore`
- [ ] Task 2: 瀏覽器管理模組
  - Create: `scraper/browser.py`, `tests/test_browser.py`

## Section B: 爬蟲核心 (待做)
- [ ] Task 3: Instagram 爬蟲（含 spike）
  - Create: `scraper/instagram.py`, `tests/test_instagram.py`, `tests/fixtures/ig_post.json`
- [ ] Task 4: Threads 爬蟲（含 spike）
  - Create: `scraper/threads.py`, `tests/test_threads.py`, `tests/fixtures/threads_post.json`

## Section C: 媒體處理 (待做)
- [ ] Task 5: 圖片 OCR（claude --print）
  - Create: `media/ocr.py`, `tests/test_ocr.py`
- [ ] Task 6: 影片逐字稿（ffmpeg + mlx-whisper）
  - Create: `media/transcriber.py`, `tests/test_transcriber.py`

## Section D: 服務整合 (待做)
- [ ] Task 7: Google Sheet 讀寫
  - Create: `services/sheet.py`, `tests/test_sheet.py`
- [ ] Task 8: LLM 摘要（claude --print）
  - Create: `services/summarizer.py`, `tests/test_summarizer.py`

## Section E: 整合 (待做)
- [ ] Task 9: 主控流程
  - Create: `main.py`, `tests/test_main.py`
- [ ] Task 10: 端對端整合測試
  - Create: `tests/test_integration.py`

## Notes
- 零 API 成本方案：`claude --print`（走 Max 額度）+ `mlx-whisper`（本地 M1 加速）
- Task 3、4 包含 spike 步驟，需要用真實 URL 探索頁面 JSON 結構
- Patchright 限制：不能與已開啟的 Chrome 共存，執行前需先關閉 Chrome
