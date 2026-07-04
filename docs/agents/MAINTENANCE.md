# 維護協議（MAINTENANCE）

> 這套制度檔本身怎麼維護。讀者：任何等級的模型。

## 1. 檔案權限分級

### 可自行修改（改前備份同目錄 `*.bak-YYYYMMDD`，改後記 LESSONS）
- `docs/agents/LESSONS.md` — 隨時追加，這是預設的教訓落點
- `docs/agents/PROMPT_TEMPLATES.md` — 範本可依實戰微調
- `docs/agents/DIAGNOSIS.md` — 排名變了就更新
- `docs/agents/MODEL_DISPATCH.md` §0 模型表 — harness 宣告變了就同步（其餘章節見下級）
- `docs/agents/LETTER_TO_FUTURE_SESSIONS.md` — 可追加註記，不可刪改原文
- 記憶目錄（`~/.claude/projects/.../memory/`）— 照記憶機制規則

### 動之前先問使用者
- `CLAUDE.md` 的**結構**（索引表、章節增刪）— 內容小修正可以，重排要問
- `docs/agents/MODEL_DISPATCH.md` §1-5、`JUDGMENT_RUBRICS.md`、`MAINTENANCE.md` 本檔 — 這是制度核心，發現規則錯誤先在 LESSONS 記「建議修改 + 理由」，由使用者裁決
- `sector_config.py`、`backend/auth.py`、`render.yaml`、`.github/workflows/`、任何 secret/env
- 刪任何不是自己建立的檔案

### 絕不自行動
- 生產環境設定（Render/Vercel/Supabase 後台、GitHub secrets）
- `git push --force`、改寫已 push 的歷史

## 2. 踩雷教訓寫哪、什麼格式

寫進 `docs/agents/LESSONS.md`，一條一段，格式：

```
## YYYY-MM-DD <一句話標題>
- 情境：當時在做什麼
- 雷：踩到什麼（錯誤訊息引原文）
- 修法：下次照做的具體步驟
- 影響檔案：<路徑>（若有）
```

判準：**「下一個 session 的模型會不會再踩」** — 會，就記；只是這次手滑，不記。
同一顆雷第二次被記 → 升級處理：把修法直接寫進 DIAGNOSIS.md 或 CLAUDE.md 地雷區（常載，成本高，所以要第二次才升）。

## 3. 精簡節奏（防制度肥大）

| 檔案 | 上限 | 超過怎辦 |
|------|------|----------|
| `CLAUDE.md` | 150 行 | 內容抽到引用檔，只留索引行 |
| `LESSONS.md` | 30 條 | 合併同類、刪已寫進 DIAGNOSIS/CLAUDE.md 的、刪過時的 |
| `docs/agents/` 其他各檔 | 120 行 | 拆檔或刪低價值段落（先問使用者） |

檢查時機：每次要**追加**內容到某檔時，順手看行數（`wc -l`），超標就先精簡再加。

## 4. 制度生效機制（重要）

這些檔**不會自動載入**。生效靠 CLAUDE.md 的索引表（常載）把讀者路由過來。因此：
- 新增制度檔 → 必須在 CLAUDE.md 索引表加一列，否則等於沒寫。
- 索引表的「情境」欄要寫**觸發情境**（何時讀），不是檔案簡介。
- 每季（或使用者要求時）派 fresh agent 驗一次：索引表列的路徑都存在、制度檔互相引用沒斷鏈。
