# Social Scraper — Implementation Plan

> **完整 plan 見**: `docs/plans/2026-02-19-social-scraper-implementation.md`
> **設計文件見**: `docs/plans/2026-02-19-social-scraper-design.md`

## 前置條件
- Branch: `feat/social-scraper`
- 最後 commit: `ea4845b` (docs: 更新實作計劃)
- 環境：ffmpeg v8.0.1, Python 3.12+, claude CLI 2.1.39 (Max 5x), M1 Mac
- credentials.json 已就位，Google Sheet 已共享

## 執行順序

```
Task 1 (骨架) → Task 2 (瀏覽器)
                    ↓
            ┌───────┴───────┐
            ↓               ↓
      Task 3 (IG)     Task 4 (Threads)   ← 可並行但都依賴 spike
            └───────┬───────┘
            ┌───────┴───────┐
            ↓               ↓
      Task 5 (OCR)    Task 6 (STT)       ← 可並行
            └───────┬───────┘
                    ↓
              Task 7 (Sheet)              ← 獨立，可提前做
                    ↓
              Task 8 (摘要)
                    ↓
              Task 9 (主控)
                    ↓
              Task 10 (E2E)
```

## 各 Task 摘要

| # | 做什麼 | 關鍵檔案 | 驗證方式 |
|---|--------|----------|----------|
| 1 | uv 初始化、config、目錄結構 | `pyproject.toml`, `config.py` | `uv sync` 成功 |
| 2 | Patchright 瀏覽器 + UA/viewport 輪替 | `scraper/browser.py` | `pytest tests/test_browser.py` |
| 3 | IG 貼文爬取（spike 探索 JSON → 解析器） | `scraper/instagram.py` | fixture-based 單元測試 |
| 4 | Threads 貼文爬取（spike 探索 JSON → 解析器） | `scraper/threads.py` | fixture-based 單元測試 |
| 5 | 圖片 OCR via `claude --print --image` | `media/ocr.py` | mock subprocess 測試 |
| 6 | 影片→ffmpeg→mlx-whisper 本地 STT | `media/transcriber.py` | ffmpeg 真實測試 + mock whisper |
| 7 | gspread 讀 A 欄 URL、寫 B/C 欄 | `services/sheet.py` | mock worksheet 測試 |
| 8 | `claude --print` 產摘要 | `services/summarizer.py` | mock subprocess + format 測試 |
| 9 | 主控流程串接所有模組 | `main.py` | `detect_platform` 單元測試 |
| 10 | 真實 URL 端對端測試 | `tests/test_integration.py` | 真實環境跑 `python main.py` |

## 技術要點

- **Spike 步驟**（Task 3、4）：先用 Patchright 開真實頁面，dump 嵌入 JSON，分析結構後才寫 parser。JSON 路徑會因 Meta 更新而變，parser 使用遞迴搜尋而非硬編碼路徑
- **claude --print 注意事項**：走 Pro/Max 額度不花 API；輸出偶帶思考殘留，需要 `.strip()`；每次呼叫是獨立 subprocess
- **Patchright 限制**：不能與已開啟的 Chrome 共存，執行前需先關閉所有 Chrome
- **mlx-whisper**：首次執行自動下載模型（~1.5GB），之後使用本地快取
- **Google Sheet 欄位**：A=社群連結、B=原始內容（【貼文文字】【圖片文字】【影片逐字稿】）、C=AI 摘要
