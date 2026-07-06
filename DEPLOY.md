# BamHI Quant 上架教學（前端 Vercel + 後端 Render）

> 架構：同一個 GitHub repo，`frontend/` 上 Vercel、`backend/` 上 Render、資料庫/登入用 Supabase（已設定好）。
> 全程不用改程式，只要在兩個平台點設定 + 填環境變數。

```
GitHub repo (bamhi-web-2.0)
 ├── frontend/  →  Vercel   (網站)
 └── backend/   →  Render   (API)         ← 兩者都連到同一個 repo
            ↘ Supabase (登入)
```

---

## Step 0 · 先確認本地能跑（很重要）

部署前先確定本地登入、頁面都正常（你已經在測了）。本地 OK 再往下，否則線上出錯會很難判斷。

---

## Step 1 · 推上 GitHub

在專案根目錄開終端機：

```bash
git add frontend backend render.yaml DEPLOY.md DEVELOPMENT.md
git commit -m "feat: Vue3 前端 + FastAPI 後端 + 部署設定"
git push
```

> `backend/.env`、`node_modules`、`dist` 都已被 gitignore，不會上傳，放心。

---

## Step 2 · 後端上 Render

1. 到 <https://render.com> 註冊/登入（可用 GitHub 帳號）
2. 右上 **New +** → **Blueprint**
3. 選你的 repo `bamhi-web-2.0` → Render 會自動讀到 `render.yaml`
4. 它會顯示要建立一個服務 `bamhi-quant-api`，按 **Apply**
5. 第一次部署前，它會要你填 **環境變數**（render.yaml 標了 `sync: false` 的那兩個）：
   - `SUPABASE_URL` = `https://vgbmwlxrmxlptptdjauy.supabase.co`
   - `FRONTEND_ORIGIN` = 先**留空或隨便填**，等 Step 3 拿到 Vercel 網址再回來改
6. 等它跑完（第一次約 3–5 分鐘）。成功後最上面會有一個網址，例如
   **`https://bamhi-quant-api.onrender.com`** ← 把它複製起來（這是你的「後端網址」）
7. 開 `<後端網址>/health` 確認顯示 `{"status":"ok",...}`

> ⚠️ Render 免費方案閒置會休眠，**第一次打開網站可能要等 30–60 秒**喚醒，正常現象。

---

## Step 3 · 前端上 Vercel

1. 到 <https://vercel.com> 註冊/登入（用 GitHub 帳號）
2. **Add New** → **Project** → 選你的 repo `bamhi-web-2.0` → **Import**
3. 關鍵設定：
   - **Root Directory** → 點 **Edit** → 選 **`frontend`** （一定要設，不然會抓錯）
   - Framework 會自動偵測為 **Vite**（不用改）
4. 展開 **Environment Variables**，加這三個：

   | Name | Value |
   |------|-------|
   | `VITE_API_BASE_URL` | Step 2 的後端網址（例 `https://bamhi-quant-api.onrender.com`） |
   | `VITE_SUPABASE_URL` | `https://vgbmwlxrmxlptptdjauy.supabase.co` |
   | `VITE_SUPABASE_ANON_KEY` | `sb_publishable_Qd8wXeNjgxLhWyRHYeMaTA_jw_AN9lB` |

5. 按 **Deploy**，等 1–2 分鐘
6. 完成後拿到你的網站網址，例如 **`https://bamhi-web-2.xxx.vercel.app`** ← 複製起來

---

## Step 4 · 回頭把兩邊接起來（CORS）

1. 回 **Render** → 你的服務 → **Environment** → 把 `FRONTEND_ORIGIN` 改成 Step 3 的 Vercel 網址
   （例 `https://bamhi-web-2.xxx.vercel.app`，結尾不要加 `/`）→ Save（會自動重新部署）

2. 到 **Supabase** Dashboard → **Authentication** → **URL Configuration**：
   - **Site URL** 填你的 Vercel 網址
   - **Redirect URLs** 也把 Vercel 網址加進去

---

## Step 5 · 測試上線版

1. 開你的 Vercel 網址
2. 第一次後端要喚醒，登入頁載入後註冊/登入若卡住，等 1 分鐘再試
3. 登入 → 各頁面應該都有資料

完成！之後你每次 `git push`，Vercel 和 Render 都會自動重新部署最新版。

---

## 常見問題

| 症狀 | 解法 |
|------|------|
| 網站打開全白 / 一直轉 | 後端在休眠，等 30–60 秒後重整 |
| 頁面有畫面但表格空白、Console 出現 CORS 紅字 | `FRONTEND_ORIGIN`(Render) 沒設對，或結尾多了 `/` |
| 登入按了沒反應 / 401 | Vercel 三個 `VITE_` 環境變數沒填對；或 Supabase 沒把 Vercel 網址加進 Redirect URLs |
| Render 部署失敗 | 看 Logs；通常是某套件裝不起來，把錯誤貼給我 |
| 每天資料更新後一直重新部署 | 正常（每日 pipeline commit 觸發）。在意的話可在 Vercel/Render 設定忽略純資料變更，之後再弄 |

---

## 備忘：環境變數總表

**Vercel（前端）**
- `VITE_API_BASE_URL` = Render 後端網址
- `VITE_SUPABASE_URL` = `https://vgbmwlxrmxlptptdjauy.supabase.co`
- `VITE_SUPABASE_ANON_KEY` = `sb_publishable_...`

**Render（後端）**
- `SUPABASE_URL` = `https://vgbmwlxrmxlptptdjauy.supabase.co`
- `FRONTEND_ORIGIN` = Vercel 網址
- （`PYTHON_VERSION` 已在 render.yaml 設好，不用管）

---

## Dual Pool Stage 2 — Render 執行設定

Stage 2（EDGAR 抓取 + LLM 抽取）從 GitHub Actions 移到 Render 執行。
背景：SEC 封鎖 GitHub Actions IP 段（data.sec.gov / www.sec.gov 均 403），
Render 後端 IP 可正常連線。GitHub Actions 每晚只當鬧鐘，curl 觸發 Render。

### Render 環境變數（新增）

| 變數 | 說明 |
|------|------|
| `DUAL_POOL_TRIGGER_TOKEN` | 自產隨機字串（`openssl rand -hex 32`），GitHub Actions 用此驗身觸發 stage2 |
| `GEMINI_API_KEY` | Gemini Flash 免費層（LLM 抽取主力；未設時自動降規則引擎，可後補） |
| `SUPABASE_SERVICE_KEY` | 確認已設（edgar_processed 表 + events 表讀寫） |
| `EDGAR_USER_AGENT` | 可選，預設 `BamHI research frank940702@gmail.com` |

### GitHub Secrets（新增）

| 變數 | 說明 |
|------|------|
| `DUAL_POOL_TRIGGER_TOKEN` | 與 Render 設定同值（Actions 呼叫 POST 用） |
| `RENDER_API_URL` | Render 後端 URL，結尾不加 `/`（如 `https://bamhi-quant-api.onrender.com`） |

### Supabase 建表（一次性）

在 Supabase SQL editor 執行 `docs/sql/dual_pool_processed.sql`。
此表（edgar_processed）持久化已處理的 EDGAR accession number，
解決 Render 暫態檔案系統問題（每次部署歸零 → stage2 重回補 90 天）。

### 確認清單

- [ ] Render 環境變數已設（至少 `DUAL_POOL_TRIGGER_TOKEN` + `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`）
- [ ] GitHub Secrets 已設（`DUAL_POOL_TRIGGER_TOKEN` + `RENDER_API_URL`）
- [ ] `docs/sql/dual_pool_processed.sql` 已在 Supabase 執行
- [ ] 本機驗收：`POST /api/dual-pool/run-stage2`（401/202）+ `GET /api/dual-pool/stage2-status`
