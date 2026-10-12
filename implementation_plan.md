# LINE Bot → Google Sheet 整合 Implementation Plan

## Goal Description
建立 LINE Bot webhook server，讓使用者在 LINE 傳送社群連結，Bot 自動寫入 Google Sheet A 欄，接入現有的 scraper 流程。

## User Review Required
> **NOTE**
> - **LINE Official Account**：需要使用者自行到 [LINE Developers Console](https://developers.line.biz/) 建立 Messaging API channel，取得 Channel Secret + Channel Access Token
> - **框架選擇**：FastAPI（輕量、async、與現有 codebase 風格一致）
> - **部署平台**：先本地開發驗證，部署方案由使用者決定（Railway / Render / VPS 等）
> - **觸發 scraper**：Bot 寫入 Sheet 後，可選擇自動觸發 scraper 或維持手動執行
> - **URL 驗證**：只接受 instagram.com / threads.net 連結，其他忽略並回覆提示

## Proposed Changes

### Project Structure
```
social-scraper/
├── linebot/
│   ├── __init__.py
│   ├── app.py            # FastAPI webhook server
│   └── line_handler.py   # LINE 訊息處理邏輯（提取 URL、驗證、回覆）
├── services/
│   └── sheet.py           # [MODIFY] 新增 append_url() 函式
├── .env.example           # [MODIFY] 新增 LINE_CHANNEL_SECRET、LINE_CHANNEL_ACCESS_TOKEN
├── config.py              # [MODIFY] 新增 LINE 相關設定
└── tests/
    ├── test_line_handler.py  # LINE 訊息解析測試
    └── test_sheet.py         # [MODIFY] 新增 append_url 測試
```

### Components

- `[NEW] linebot/app.py`
  FastAPI 應用，掛載 LINE webhook endpoint (`POST /callback`)，驗證 signature，分派訊息

- `[NEW] linebot/line_handler.py`
  從 LINE 訊息中提取 URL → 驗證是否為支援平台 → 呼叫 sheet.append_url() → 回覆使用者

- `[MODIFY] services/sheet.py`
  新增 `append_url(url: str)` — 將 URL 寫入 Sheet A 欄下一空行，回傳寫入的列號

- `[MODIFY] config.py`
  新增 `LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN` 環境變數

- `[MODIFY] .env.example`
  新增 LINE 相關環境變數範例

- `[NEW] tests/test_line_handler.py`
  測試 URL 提取、平台驗證、無效訊息處理

## Verification Plan

### Manual Verification
1. 啟動 FastAPI server (`uvicorn linebot.app:app`)
2. 用 ngrok 暴露本地 port，設定為 LINE webhook URL
3. 在 LINE 傳送 IG/Threads 連結 → 確認 Google Sheet 新增一列
4. 傳送無效連結 → 確認 Bot 回覆提示訊息
5. 傳送純文字（非 URL）→ 確認 Bot 忽略或提示

### Automated Tests
- LINE 訊息 URL 提取邏輯（mock LINE SDK）
- 平台驗證（instagram.com / threads.net / 不支援的 URL）
- sheet.append_url() 寫入正確位置
