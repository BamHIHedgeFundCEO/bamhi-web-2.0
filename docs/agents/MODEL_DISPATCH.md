# 模型調度守則（MODEL_DISPATCH）

> 目的：主對話（指揮官）的 context 與額度是最貴的資源。凡是「換便宜模型不掉品質」的工作，一律派 subagent。
> 主對話只做：拆解任務、寫交辦 prompt、整合結論、做便宜模型做不了的判斷。

## 0. 已查證的模型實值（2026-07-04 查自 harness；改動前先重查）

| 別名 | Model ID | Agent 工具 `model` 參數值 | 用途定位 |
|------|----------|--------------------------|----------|
| Fable 5 | `claude-fable-5` | `fable` | 最貴，**不要用於 subagent**；只有使用者明說才用 |
| Opus 4.8 | `claude-opus-4-8` | `opus` | 難題升級目標 |
| Sonnet 4.6 | `claude-sonnet-4-6` | `sonnet` | 預設工作馬 |
| Haiku 4.5 | `claude-haiku-4-5-20251001` | `haiku` | 機械性工作（此 ID 原生含日期後綴，非筆誤；查自 harness 宣告） |

- 本 session 的 Agent 工具參數只有 `model`（已查 schema）；effort 不能在派工當下指定，要用下面的機制。

### Effort 設定（2026-07-04 查自官方文件 code.claude.com/docs）

| 機制 | 用法 | 有效值 |
|------|------|--------|
| `/effort` 指令 | `/effort <level>`，`/effort auto` 重設 | `low` `medium` `high` `xhigh` `max`（依模型而異） |
| CLI 旗標 | `claude --effort <level>` | 同上 |
| 環境變數 | `CLAUDE_CODE_EFFORT_LEVEL`（優先級最高） | 同上 |
| settings.json | `"effortLevel": "..."` | 只收 `low` `medium` `high` `xhigh` |
| subagent frontmatter | 自訂 agent 定義檔加 `effort:` 欄位 | 同上，覆蓋 session 層級 |

- 用法原則：機械性批次工作（haiku/sonnet 派工）用 `low`/`medium` 就夠；升級到 opus 解難題時才配 `high`/`xhigh`。
- subagent model 解析順序：`CLAUDE_CODE_SUBAGENT_MODEL` env > 派工時 `model` 參數 > frontmatter `model` > 繼承主對話。
- 出處：<https://code.claude.com/docs/en/sub-agents.md>、<https://code.claude.com/docs/en/model-config.md>。文件範例中出現 `claude-sonnet-5`，但本 harness 宣告最新為 Sonnet 4.6 — 以各 session 的 harness 宣告為準。

## 1. 指揮官不下場（鐵律）

主對話**禁止**親自做以下事，一律派 subagent：

| 工作 | 派誰 | model |
|------|------|-------|
| 找定義/呼叫點/列出用法（「X 在哪」） | `caveman:cavecrew-investigator` | `haiku` |
| 廣域掃 repo、多目錄多命名慣例搜尋 | `Explore` | `haiku`（複雜時 `sonnet`） |
| 1-2 檔的機械修改（typo、rename、單函式改寫） | `caveman:cavecrew-builder` | `sonnet` |
| diff / 檔案審查 | `caveman:cavecrew-reviewer` | `sonnet` |
| 多檔實作、跨檔重構 | `general-purpose` | `sonnet` |
| 網路研究、文件查證 | `general-purpose`（或 `claude-code-guide` 查 Claude Code 問題） | `sonnet` |
| 規劃實作方案 | `Plan` | `sonnet`，難題 `opus` |
| 驗證別人的產出 | fresh `general-purpose` | `haiku`（read-back）/ `sonnet`（跑測試） |

例外（主對話可以自己做）：≤3 個工具呼叫能完成、且進入主對話的工具結果總計少於 50 行的事（例如改一行、跑一個已知指令）。派工的固定成本比自己做還高時就自己做。

## 2. 交辦三要素（每個 subagent prompt 必含）

1. **目標與動機**：做什麼 + 為什麼（讓 subagent 遇到歧義能自行判斷方向）。
2. **驗收條件**：可機械檢查的完成定義（「X 檔存在且含 Y」「測試 Z 通過」「回傳表格含欄位 A,B,C」）。
3. **回報格式**：明定格式與長度上限。

範本見 [PROMPT_TEMPLATES.md](PROMPT_TEMPLATES.md)。三要素缺一，先補再派。

## 3. 回報合約（subagent 端的規則，寫進交辦 prompt）

- 只回**結論**與 `檔案:行號`，不要貼大段程式碼或檔案內容。
- 產物超過 30 行 → 存檔（scratchpad 或指定路徑），回傳路徑 + 3 行摘要。
- 失敗要回「失敗軌跡」：試了什麼、錯誤原文（exact quote）、卡在哪。禁止只回「失敗了」。
- 沒把握的內容標 `[未確認]`，禁止編造路徑、參數、model id。

## 4. 升降級路徑

- **haiku 錯 1 次** → 同任務升 `sonnet` 重派（附 haiku 的失敗軌跡）。
- **sonnet 同一子任務連錯 2 次** → 升 `opus`，交辦 prompt 必附完整失敗軌跡（兩次都做了什麼、錯誤原文、已排除的假設）。
- **opus 也解不了** → 停，回報使用者（見 JUDGMENT_RUBRICS「何時停下來問」）。不要動用 `fable`。
- **解出模式後降級**：opus/sonnet 解出一個實例後，把解法寫成步驟化指令，降回 `sonnet`/`haiku` 批次套用到其餘實例。
- **停損線（唯一定義，別檔引用以此為準）**：同一子任務在**同一模型層級**最多嘗試 2 次（含換方法）；升級鏈 haiku→sonnet→opus 走到底仍失敗，或 opus 已試 2 次 → 停下回報使用者。禁止在任何層級嘗試第 3 次。

## 5. 驗證不自驗（鐵律）

做的人不驗自己的產出。驗證一律派 **fresh-context** agent（不帶做事者的對話歷史）：

| 產物類型 | 驗法 |
|----------|------|
| 檔案/文件 | read-back：新 agent 讀檔，回答「檔案存在？內容完整？與規格矛盾處？」 |
| 程式碼 | 跑測試或實跑（curl 端點、pytest、npm run build），貼結果原文 |
| 高風險判斷（架構、刪東西、對外動作） | 第二意見：另派一個 agent 獨立判斷，或產 2-3 個候選答案後派 reviewer 擇優 |

驗證 agent 的 prompt 要寫「找碴，不是背書」——明確要求列出問題而非確認沒問題。

## 6. 待確認事項（查不到就不要編）

- subagent 的 token 是否與主對話共用同一個用量窗口：**部分確認** — 官方文件顯示 subagent 走同一組帳號/訂閱（會回同型 usage limit 錯誤），但沒有明文寫「共用同一 rate-limit 池」。實務上當作共用來管理預算。
- 「被安全機制導向 Opus 4.8 的請求是否消耗本窗口額度」：**未確認**，建議到 claude.ai/settings/usage 儀表板實測前後用量。
- 模型名單會過時：任何 session 引用本檔前，以 harness 環境區塊宣告的 model id 為準；不一致時更新本檔第 0 節並記到 LESSONS.md。
