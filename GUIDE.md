# Social Scraper — 操作手冊

## 目錄

1. [環境準備](#環境準備)
2. [LINE Bot 模式（日常使用）](#line-bot-模式日常使用)
3. [批次模式](#批次模式)
4. [Google Sheet 操作](#google-sheet-操作)
5. [GitHub Token 設定（可選）](#github-token-設定可選)
6. [常見問題排除](#常見問題排除)
7. [開發者指引](#開發者指引)

---

## 環境準備

### 一次性安裝

```bash
# 安裝依賴
uv sync

# 安裝瀏覽器引擎（IG/Threads 需要）
uv run patchright install chromium

# 設定環境變數
cp .env.example .env
```

### `.env` 必填欄位

```env
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/你的ID/edit
GOOGLE_CREDENTIALS_PATH=credentials.json
LINE_CHANNEL_SECRET=你的_secret
LINE_CHANNEL_ACCESS_TOKEN=你的_token
```

### `.env` 選填欄位

```env
# 提升 GitHub API 限額（60 → 5000 req/hr）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Notion Integration（網頁全文存 Notion 用）
NOTION_TOKEN=ntn_xxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Claude CLI 路徑（預設 "claude"）
CLAUDE_CLI=/usr/local/bin/claude

# mlx-whisper 模型（預設 large-v3-turbo）
WHISPER_MODEL=mlx-community/whisper-large-v3-turbo
```

---

## LINE Bot 模式（日常使用）

這是最主要的使用方式。在 LINE 傳連結給 Bot，自動處理並寫回 Google Sheet。

### 啟動步驟

```bash
# 步驟 1：關閉 Chrome（Patchright 限制，IG/Threads 必需）
pkill -f "Google Chrome"

# 步驟 2：啟動 server
uv run uvicorn line_webhook.app:app --port 8000 &

# 步驟 3：啟動 ngrok（另一個終端視窗）
ngrok http 8000
```

### 設定 LINE Webhook（每次 ngrok 重啟後都要做）

1. 複製 ngrok 顯示的 HTTPS URL（例：`https://abc123.ngrok-free.app`）
2. 到 [LINE Developers Console](https://developers.line.biz/)
3. 進入你的 Channel → **Messaging API** 分頁
4. **Webhook URL** → 貼上 `https://abc123.ngrok-free.app/callback`
5. 確認 **Use webhook** 已開啟
6. 點 **Verify** 確認連線成功

### 傳送連結

在 LINE 聊天室中直接傳送連結：

| 傳送內容 | 處理方式 | 寫入位置 |
|----------|----------|----------|
| `https://www.instagram.com/p/xxx/` | Patchright 爬取 + OCR + 摘要 | Sheet1 |
| `https://www.threads.net/@user/post/xxx` | Patchright 爬取 + OCR + 摘要 | Sheet1 |
| `https://github.com/owner/repo` | GitHub API + README 摘要 | GitHub 工作表 |
| 其他網頁 URL（如 bnext.com.tw） | httpx + readability 全文擷取 | Notion Database |

Bot 會先立即回覆「已收到，排入佇列」，背景處理完成後再推播結果（含 Notion 頁面連結）。

### 停止 server

```bash
# 找到 server PID
lsof -i :8000

# 停止
kill <PID>
```

---

## 批次模式

適用於一次處理大量 URL。

### 操作流程

1. **在 Google Sheet 手動貼入 URL**
   - IG/Threads URL → **Sheet1** 的 A 欄
   - GitHub URL → **GitHub 工作表** 的 A 欄
   - B 欄留空（系統用 B 欄判斷是否待處理）

2. **執行批次處理**
   ```bash
   pkill -f "Google Chrome"    # IG/Threads 需要
   uv run python main.py
   ```

3. **執行順序**：先處理 GitHub 工作表，再處理 Sheet1
4. **每日上限**：各 30 筆（`config.py` 的 `DAILY_LIMIT`）

---

## Google Sheet 操作

### Sheet1（IG/Threads）

| 欄 | 內容 | 誰填 |
|----|------|------|
| A | 社群連結 | 手動貼 / LINE Bot 自動 |
| B | AI 摘要 | 系統自動 |
| C | 關鍵點 | 系統自動 |
| D | 執行日期 | 系統自動 |

### GitHub 工作表（首次使用時自動建立）

| 欄 | 內容 | 誰填 |
|----|------|------|
| A | Repo URL | 手動貼 / LINE Bot 自動 |
| B | Repo 名稱（owner/repo） | 系統自動 |
| C | 官方說明（description） | 系統自動 |
| D | README 中文摘要（5~10 句） | 系統自動 |
| E | 使用情境（3~5 個 bullet） | 系統自動 |
| F | 星數/語言（⭐ 1234 \| Python） | 系統自動 |
| G | 日期 | 系統自動 |

### 判斷邏輯

- **A 欄有值 + B 欄為空** = 待處理
- **A 欄有值 + B 欄有值** = 已處理（跳過）
- **B 欄為 `[ERROR] ...`** = 處理失敗，可清空 B 欄重新觸發

---

## GitHub Token 設定（可選）

不設 token 也能用，但有 API 限額差異：

| | 無 Token | 有 Token |
|---|---------|----------|
| 限額 | 60 req/hr | 5,000 req/hr |
| 適用 | 偶爾用 | 大量批次 |

### 產生 Token

1. 到 [GitHub Settings → Tokens](https://github.com/settings/tokens)
2. **Generate new token (classic)**
3. 勾選 `public_repo` scope（只需讀取公開 repo）
4. 複製 token，加入 `.env`：
   ```
   GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
   ```

---

## Notion 設定（網頁全文存檔用）

### 首次設定

1. 到 [Notion Integrations](https://www.notion.so/my-integrations) 建立 Internal Integration → 取得 token
2. 在 Notion 建立一個頁面，將 Integration 加入該頁面的 Connections
3. 透過 API 或手動建立 Database，欄位：Title / URL / Source / Published / Tags / Saved
4. 將 token 和 database ID 填入 `.env`

### Notion Database 欄位

| 欄位 | 類型 | 內容 |
|------|------|------|
| Title | Title | 文章標題 |
| URL | URL | 原始連結（已清除追蹤參數） |
| Source | Select | 來源網站（如 bnext.com.tw） |
| Published | Date | 文章發布日期 |
| Tags | Multi-select | 文章標籤 |
| Saved | Date | 擷取日期 |

頁面內容為純文章正文。

---

## 常見問題排除

### Bot 沒反應

```bash
# 1. 確認 server 在跑
lsof -i :8000

# 2. 確認 ngrok 在跑
# 瀏覽器開 http://127.0.0.1:4040 看 ngrok dashboard

# 3. 確認 Webhook URL 正確
# LINE Developers Console → Messaging API → Webhook URL → Verify
```

### 斷網後恢復

```bash
# ngrok 斷了要重開
ngrok http 8000
# 拿新 URL 去 LINE Console 更新 Webhook URL

# server 也斷了的話
uv run uvicorn line_webhook.app:app --port 8000 &
```

### IG 爬取失敗

- 確認 Chrome 已全部關閉：`pkill -f "Google Chrome"`
- 部分貼文需要登入（私人帳號），無法匿名存取
- 網路不穩定時可能逾時，重新處理即可（清空 B 欄）

### GitHub 處理失敗

- 確認 repo 存在且為公開
- 私有 repo 需設定有存取權限的 `GITHUB_TOKEN`
- API 超過限額會返回 403，等一小時或設定 token

---

## 開發者指引

### 測試

```bash
# 全部單元測試（72 個）
uv run pytest tests/ -v --ignore=tests/test_integration.py

# 整合測試（需真實環境）
uv run pytest tests/test_integration.py -v -m integration -s

# 單獨跑 GitHub 相關測試
uv run pytest tests/test_github.py tests/test_github_summarizer.py -v
```

### 專案結構

```
social-scraper/
├── main.py                      # 批次入口（GitHub + IG/Threads）
├── config.py                    # 環境變數 + 常數
├── line_webhook/
│   ├── app.py                   # FastAPI webhook server
│   └── line_handler.py          # URL 提取（IG/Threads/GitHub）
├── scraper/
│   ├── browser.py               # Patchright 瀏覽器管理
│   ├── instagram.py             # IG 貼文解析
│   ├── threads.py               # Threads 貼文解析
│   ├── github.py                # GitHub REST API 爬取
│   └── article.py               # 一般網頁全文擷取
├── media/
│   ├── ocr.py                   # 圖片 OCR + run_claude_print()
│   └── transcriber.py           # 影片 → mlx-whisper
├── services/
│   ├── sheet.py                 # Google Sheet（Sheet1 + GitHub）
│   ├── summarizer.py            # IG/Threads 摘要
│   ├── github_summarizer.py     # GitHub README 摘要
│   └── notion.py                # Notion Database 寫入
└── tests/                       # 單元測試
```

### 相關文件

- [PLAN.md](PLAN.md) — 設計決策與計劃索引
- [task.md](task.md) — 實作進度追蹤
- [implementation_plan.md](implementation_plan.md) — 最新功能實作計劃
