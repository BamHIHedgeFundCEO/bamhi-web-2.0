# BamHI Quant v2.0 — 本地開發啟動指南

把舊的 Streamlit 儀表板遷移為 **Vue 3 前端 + FastAPI 後端** 的雙層架構。

```
bamhi-web-2.0/
├── frontend/        Vue 3 + Vite      → 之後部署到 Vercel
├── backend/         FastAPI           → 之後部署到 Render
├── data_engine/     ┐ 資料大腦（被 backend 重用，沿用既有程式）
├── data_pipeline/   ┘
├── data/            每日 pipeline 產出的 CSV
└── app.py / views/  舊版 Streamlit（暫時保留作對照，遷移完成後可移除）
```

> 你需要開**兩個終端機**：一個跑後端 (port 8000)，一個跑前端 (port 5173)。

---

## 🚀 最速啟動（免登入預覽模式）

目前前後端都預設開啟「免登入預覽開關」，**不需要申請 Supabase 就能直接看畫面**。

### 終端機 1 — 後端 (FastAPI)

```bash
# 在專案根目錄 bamhi-web-2.0/
cd backend
pip install -r requirements.txt          # 第一次才需要

cd ..                                     # ⚠️ 回到專案根目錄再啟動
uvicorn backend.main:app --reload --port 8000
```

啟動成功後開 <http://localhost:8000/health> 應看到 `{"status":"ok",...}`。

> `backend/.env` 已內含 `AUTH_DISABLED=true`（此檔已被 gitignore，不會上傳）。

### 終端機 2 — 前端 (Vue)

```bash
cd frontend
npm install                               # 第一次才需要
npm run dev
```

瀏覽器開 <http://localhost:5173> → 因為 `frontend/.env.development` 的
`VITE_AUTH_DISABLED=true`，會**直接進入儀表板**，不會被導去登入頁。

### 可瀏覽的頁面

> 現在所有頁面共用頂部**導覽列**：Logo｜首頁｜總經市場｜交易工具▾（暗池/板塊輪動/板塊強弱/全球強弱）｜交易模型｜右上角**個股搜尋框**（輸入 AAPL 按 Enter）。直接點導覽即可互相切換，不必再改網址列。

| 路由 | 模組 |
|------|------|
| <http://localhost:5173/> | 首頁（Hero + 板塊即時訊號推播，點卡片進板塊輪動） |
| <http://localhost:5173/search?q=AAPL> | 個股深度搜尋（價格/估值/K線+量化分數/公司資料/財報） |
| <http://localhost:5173/macro> | 總經市場（6 指標 + 時間區間 + ECharts） |
| <http://localhost:5173/dark-pool> | 暗池異常資金監控（Top 50 表格） |
| <http://localhost:5173/sector-strength> | 美股板塊強弱（RS 線 + 熱力圖 + 總覽表 + 策略掃描，點列鑽取成分股） |
| <http://localhost:5173/world-sectors> | 全球市場強弱（動能熱力圖 + 各區排行 + 策略掃描） |
| <http://localhost:5173/models> | 交易模型每日戰報（Alpha / Genesis 雙引擎 + 時光機日期） |
| <http://localhost:5173/sector-rotation> | 板塊輪動 + VCP（熱力圖/RRG/軌跡/相關係數 + K線/RS/寬度/機構流/動能 + VCP 掃描） |

> ⚠️ `/sector-rotation` 首次載入會 bulk 下載全部追蹤股（數百檔），需等數十秒；之後 1 小時內走後端快取。

---

## 🔐 切換成「真正的 Supabase 登入」模式

要測試完整登入流程時：

1. 到 [Supabase](https://supabase.com) 建一個免費專案。
2. **前端** `frontend/.env.development`：
   ```
   VITE_SUPABASE_URL=https://<你的專案>.supabase.co
   VITE_SUPABASE_ANON_KEY=<Project Settings → API → anon public key>
   VITE_AUTH_DISABLED=false          # 關掉預覽 bypass
   ```
3. **後端** `backend/.env`：
   ```
   SUPABASE_JWT_SECRET=<Project Settings → API → JWT Secret>
   # 把 AUTH_DISABLED 這行刪掉或設為 false
   ```
4. 重啟前後端 → 進入 <http://localhost:5173> 會被導向 `/login`，
   可在頁面上註冊 / 登入（Supabase Auth）。

---

## 🧪 直接測後端 API（不開前端）

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/macro/series?indicator=DGS10"
curl http://localhost:8000/api/dark-pool/surge-list
```

> 免登入模式下不需帶 token；正式模式下需帶 `Authorization: Bearer <jwt>`。

可用的指標 id：`DGS10` `DGS2` `SPREAD_10_2` `MACRO_TRIO` `BREADTH_SP500` `SENTIMENT_COMBO`

---

## 🛠️ 常見問題

| 症狀 | 原因 / 解法 |
|------|------------|
| `uvicorn: command not found` | 先 `pip install -r backend/requirements.txt` |
| 後端報 `ModuleNotFoundError: backend` | 啟動指令要在**專案根目錄**執行 `uvicorn backend.main:app`，不要 `cd backend` 後再跑 |
| 前端圖表/表格空白、Console 出現 CORS 或 Network error | 後端沒開，或 port 不是 8000（對照 `frontend/.env.development` 的 `VITE_API_BASE_URL`） |
| API 回 401 | 你關了 bypass 但沒設好 Supabase 金鑰；先確認兩邊 `AUTH_DISABLED` / `VITE_AUTH_DISABLED` 一致 |
| 暗池頁顯示「暫無暗池資料」 | `data/darkpool_results.csv` 不存在，跑一次 `python data_pipeline/market/update_darkpool_pipeline.py` |

---

## 📦 之後部署（備忘，現在不用做）

- **前端 → Vercel**：Root Directory 設為 `frontend`，環境變數用 `.env.production` 那組（填真實 Supabase 值）。
- **後端 → Render**：Root Directory 設為 `backend`，Start Command
  `uvicorn backend.main:app --host 0.0.0.0 --port 10000`，環境變數設
  `SUPABASE_JWT_SECRET` 與 `FRONTEND_ORIGIN`（你的 Vercel 網址），**不要**設 `AUTH_DISABLED`。
