# Social Scraper — 技術規劃

## 目標

對 Threads 和 Instagram 上的特定內容進行爬取與 LLM 摘要。

---

## 技術路線

### 路線 1：官方 API（最穩定，優先使用）

- **Instagram Graph API** — 商業帳號可取得貼文、留言、粉絲數據。限制：只能抓自己管理或被授權的帳號
- **Threads API** — Meta 2024 年中已開放，可讀取公開貼文
- 缺點：rate limit 限制，只能拿到 Meta 開放的資料

### 路線 2：無頭瀏覽器模擬（最常見）

用 Playwright / Puppeteer 模擬真人瀏覽器行為：

```
真人操作 → 瀏覽器自動化 → 擷取頁面內容 → LLM 摘要
```

### 路線 3：攔截 Mobile API（進階）

用 mitmproxy 攔截 IG/Threads app 的 API 請求，直接重放 endpoint。速度快但 Meta 經常改 API 簽名。

**決策：先用 API 拿能拿的，不夠的部分才上爬蟲（路線 2）。**

---

## 防封策略

### IP 層

| 策略 | 說明 |
|------|------|
| 輪替代理 | 住宅代理（residential proxy）最不容易被偵測，datacenter IP 容易被封 |
| 代理池 | BrightData / Oxylabs / SmartProxy 等服務，每次請求換 IP |
| 請求頻率 | 模擬人類節奏，每次請求間隔 3-10 秒隨機延遲，不要固定間隔 |

### 瀏覽器指紋層

| 策略 | 說明 |
|------|------|
| 反指紋瀏覽器 | Camoufox（基於 Firefox）或類似工具，自動隨機化 fingerprint |
| 隱藏自動化痕跡 | Playwright stealth plugin（`playwright-extra` + `stealth`） |
| User-Agent 輪替 | 每個 session 用不同但合理的 UA |
| Canvas / WebGL | 指紋也要隨機化，同一指紋大量請求會被標記 |

### 行為層（最關鍵）

```
❌ 錯誤示範：開了就直接爬 1000 篇貼文
✅ 正確做法：
   1. 先模擬登入（或用已存在的 session cookie）
   2. 像人一樣瀏覽：先到首頁 → 搜尋 → 點進 profile → 滾動 → 才讀貼文
   3. 隨機停留時間（2-8 秒）
   4. 偶爾做無關動作（滾回去、點別的）
   5. 單帳號每天抓取量要有上限（例如 50-100 篇）
```

### 帳號層

- **多帳號輪替** — 準備多個帳號，每個帳號低頻使用
- **養號** — 新帳號先正常使用幾天再開始爬
- **Session 管理** — 存 cookie/session，不要每次重新登入（頻繁登入是 red flag）

---

## 系統架構

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ 排程器       │────▶│ 爬蟲 Worker  │────▶│ 原始資料 DB │
│ (Cron/Queue) │     │ Playwright + │     │ (PostgreSQL) │
│              │     │ Proxy Pool   │     │              │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                                          ┌──────▼──────┐
                                          │ LLM 摘要    │
                                          │ (Claude API) │
                                          └─────────────┘
```

### 元件

| 元件 | 候選技術 | 說明 |
|------|----------|------|
| 排程器 | Cron / Celery / BullMQ | 控制爬取頻率與任務分配 |
| 爬蟲引擎 | Playwright + stealth plugin | 無頭瀏覽器模擬真人行為 |
| 代理服務 | BrightData / Oxylabs / SmartProxy | 住宅代理 IP 輪替 |
| 反指紋 | Camoufox / playwright-stealth | 隱藏自動化特徵 |
| 資料儲存 | PostgreSQL / SQLite | 存原始爬取資料 |
| LLM 摘要 | Claude API | 對爬取內容產生摘要 |

---

## 成本估算

| 項目 | 月費估算 |
|------|----------|
| 住宅代理 | $30-100 |
| 多帳號維護 | 人力成本 |
| 反指紋工具 | 開源免費 or $20-50 |
| Claude API | 依用量，約 $10-50 |
| **合計** | **$50-200+/月** |

---

## 風險與注意事項

1. **Meta 反爬很強** — 有專門團隊做反自動化，長期維護成本不低
2. **帳號封禁風險** — 即使做了所有措施，帳號仍可能被停用
3. **法律灰色地帶** — 爬公開資料通常可接受，但違反 ToS 是確定的
4. **API 簽名變動** — Meta 經常更新，需持續維護

---

## TODO

- [ ] 調研 Threads API / Instagram Graph API 可取得的資料範圍
- [ ] 評估代理服務方案（BrightData vs Oxylabs vs SmartProxy）
- [ ] Playwright stealth plugin PoC
- [ ] 設計資料模型（要存哪些欄位）
- [ ] LLM 摘要 prompt 設計
- [ ] 決定技術棧（Python or Node.js）
