# BamHI Quant — CLAUDE.md

量化投資儀表板。FastAPI 後端 + Vue 3 前端，部署 Render + Vercel。
本檔只放「每次都需要的最小事實 + 索引」。細節進下方引用檔，**按需再讀，不要預先全讀**。

## 文件索引（按需讀取）

| 情境 | 讀這份 |
|------|--------|
| 要派 subagent / 選模型 / 交辦任務 | `docs/agents/MODEL_DISPATCH.md` |
| 不確定何時升級、何時算完成、何時該問使用者 | `docs/agents/JUDGMENT_RUBRICS.md` |
| 要寫交辦 prompt（搜尋/實作/重構/研究/審查） | `docs/agents/PROMPT_TEMPLATES.md` |
| 踩雷了 / 要改制度檔 / 判斷哪些檔能動 | `docs/agents/MAINTENANCE.md` + `docs/agents/LESSONS.md` |
| 為什麼有這套制度、環境三大地雷 | `docs/agents/DIAGNOSIS.md` |
| 本地開發環境啟動 | `DEVELOPMENT.md` |
| 部署（Vercel/Render/Supabase 設定） | `DEPLOY.md` |
| 換新電腦 | `SETUP.md` |
| 選股邏輯 / 戰報篩選規則 | `SCREENING_PLAYBOOK.md` |

## 架構

```
bamhi-web-2.0/
├── backend/          # FastAPI (Python 3.13)，部署 Render port 10000
│   ├── main.py       # 應用入口，掛載所有 router
│   ├── auth.py       # Supabase JWT 驗證（JWKS + HS256 fallback）
│   ├── routers/      # API 端點（每功能一檔）
│   ├── services/     # 業務邏輯（對應 routers/）
│   └── config/sectors.py  # 代理 import 根目錄 sector_config.py
├── frontend/         # Vue 3 + Vite + Pinia + ECharts，部署 Vercel
│   └── src/          # views/ stores/ components/ router/ api/client.js lib/
├── data_pipeline/    # 資料更新管線（update_data.py 呼叫；含 sanity_check.py 資料檢核）
├── data/             # 每日 pipeline 產出 CSV（機器人自動 commit）
├── legacy/           # 舊版 Streamlit 全部遺留（app.py、views/、data_engine/ 等），禁止 import，見 legacy/README.md
├── sector_config.py  # 板塊設定唯一來源（backend + pipeline 共用）
└── update_data.py    # 手動/排程資料更新（結尾自動跑 sanity check）
```

## 開發環境

- **Python**：系統 `python` 是壞捷徑，用 `C:\Users\User\anaconda3\python.exe` 或 `conda run`
- **編碼**：跑 Python 前設 `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`（中文 log 會炸）
- **Shell**：PowerShell 5.1 沒有 `&&`；POSIX 語法用 Bash 工具
- **啟動後端**：`uvicorn backend.main:app --reload --port 10000`
- **啟動前端**：`cd frontend && npm run dev`（port 5173）
- **env**：`backend/.env`（參考 `backend/.env.example`）；前端 `frontend/.env.local`

## 環境變數（backend/.env）

| 變數 | 說明 |
|------|------|
| `AUTH_DISABLED=true` | 本地開發略過 JWT，**生產絕對不設** |
| `SUPABASE_URL` | Supabase 專案 URL（JWKS 驗證用） |
| `SUPABASE_JWT_SECRET` | 僅舊版 HS256 專案需要 |
| `FRONTEND_ORIGIN` | 生產前端 URL，加入 CORS 白名單 |
| `POLYGON_API_KEY` | 資料源 |
| `DISCORD_WEBHOOK_URL` | Discord 通知（insider 大單警報 + 每日摘要） |
| `INSIDER_MEGA_THRESHOLD` | 超大單警報門檻（美元，預設 5000000） |
| `DIGEST_HOUR_EST` | 每日摘要推送時間（美東，預設 22） |

## 認證流程

- Supabase Auth；前端 `src/lib/supabase.js`，後端 `auth.py` 驗 Bearer JWT（JWKS 優先，fallback HS256）
- 路由守衛：`router/index.js` → `meta.requiresAuth` → `useAuthStore`
- 前端開發跳過：`VITE_AUTH_DISABLED=true`（只在 `import.meta.env.DEV` 生效）

## 常見地雷

- `AUTH_DISABLED=true` 只能放本地 `backend/.env`，生產 Render 絕對不設
- 後端邏輯一律寫進 `backend/services/`（純 pandas/numpy）；`legacy/`（含舊 data_engine）任何東西都**禁止 import**
- `sector_config.py` 是唯一來源，改動同時影響 `backend/` 與 `data_pipeline/`；`backend/config/sectors.py` 用 `sys.path` 插根目錄是刻意設計不是 bug
- 前端 HTTP 唯一出口是 `frontend/src/api/client.js`，元件與 store 禁止硬編碼後端 URL
- `data/*.csv`、`*.xlsx` 不要整檔讀進對話 — 用 pandas 看 shape/head（見 `docs/agents/DIAGNOSIS.md`）
- 機器人會自動 commit `data/`（訊息含 `[skip ci]`）；pull 前確認工作區乾淨

## 資料更新

```bash
python update_data.py   # 更新利率 + 市場資料（GitHub Actions 也會自動跑）
```

## 新增功能標準流程

1. `backend/routers/<name>.py` — 端點
2. `backend/services/<name>.py` — 業務邏輯
3. `backend/main.py` — `app.include_router(...)`
4. `frontend/src/stores/<name>.js` — Pinia store
5. `frontend/src/views/<Name>View.vue` — 頁面
6. `frontend/src/router/index.js` — 加 `/app/<path>` 子路由（`/app/*` 需登入）
