# 換新電腦設定指南

> 只是想「**用**」網站？不用看這份 —— 直接開 <https://bamhi-web-2-0.vercel.app> 登入即可，任何裝置免安裝。
>
> 這份是給你想在**新電腦上「改程式 / 繼續開發」**用的。照順序做一次就好。

---

## 第 1 步 · 安裝必要工具（每台電腦只需一次）

到各官網下載安裝：

1. **Git** — <https://git-scm.com/downloads>
2. **Node.js**（選 LTS 版）— <https://nodejs.org>
3. **Python 3.11+** — <https://www.python.org/downloads>（安裝時記得勾 **Add Python to PATH**）
4. **Claude Code** — 依你原本的安裝方式

裝完開一個終端機，確認都裝好（有顯示版本號就對了）：
```bash
git --version
node -v
npm -v
python --version
```

---

## 第 2 步 · 把專案抓下來

選一個你想放專案的資料夾，開終端機執行：
```bash
git clone https://github.com/BamHIHedgeFundCEO/bamhi-web-2.0.git
cd bamhi-web-2.0
```

---

## 第 3 步 · 裝前端套件

```bash
cd frontend
npm install
cd ..
```
> `frontend/.env.development` 已經在 repo 裡（含 Supabase 設定），不用補。

---

## 第 4 步 · 裝後端套件 + 補一個設定檔

```bash
cd backend
pip install -r requirements.txt
cd ..
```

⚠️ **`backend/.env` 沒有上傳 GitHub（內含設定，刻意不公開）**，新電腦要自己建一個：

在 `backend/` 資料夾新增檔案 `.env`，內容貼上：
```
SUPABASE_URL=https://vgbmwlxrmxlptptdjauy.supabase.co
AUTH_DISABLED=true
```
> `AUTH_DISABLED=true` 是本地開發免登入預覽用。要在本地測真正的登入，改成把這行刪掉，並把 `frontend/.env.development` 的 `VITE_AUTH_DISABLED` 設為 `false`。

---

## 第 5 步 · 本地啟動（開兩個終端機）

**終端機 A — 後端**（在專案根目錄 `bamhi-web-2.0/`）：
```bash
uvicorn backend.main:app --reload --port 8000
```

**終端機 B — 前端**：
```bash
cd frontend
npm run dev
```

瀏覽器開 <http://localhost:5173> 即可。詳細操作、常見問題見 **DEVELOPMENT.md**。

---

## 關於紀錄（換電腦會不會不見）

| 項目 | 會跟著走嗎 |
|------|-----------|
| 程式碼 + 所有版本歷史（GitHub） | ✅ `git clone` 就有全部 |
| 線上網站、使用者帳號（Vercel/Render/Supabase） | ✅ 雲端，本來就在 |
| **跟 Claude Code 的對話紀錄** | ❌ 存在舊電腦本機，不會跟過來 |

> 新電腦上開 Claude Code 是全新對話。但程式碼和這些 `.md` 教學都在 repo，
> 直接叫 Claude「先讀 SETUP.md、DEVELOPMENT.md、DEPLOY.md 了解專案」，它就能接手繼續幫你。

---

## 相關文件

- **DEVELOPMENT.md** — 本地開發、跑起來、常見問題
- **DEPLOY.md** — 上架（Vercel + Render）完整步驟與環境變數
