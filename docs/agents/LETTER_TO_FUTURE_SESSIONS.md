# 給未來 session 的信

寫於 2026-07-04，Fable 5 唯一一次 session。讀者：之後長期運作的 Sonnet / Opus / Haiku，以及使用者 Frank。

---

## 一、三件沒被問到、但我認為最重要的事

### 1. 這個 repo 最大的風險不是程式碼，是「資料正確性沒有防線」
整個系統的價值鏈是：pipeline 抓資料 → 算指標 → 戰報 → 使用者做投資決策。程式碼有 lint、有 build check，但**資料本身沒有任何自動驗證**——來源網站改版（NAAIM/AAII 爬蟲已發生過）、FRED/Treasury 格式變動、時區造成的日期錯位，都會安靜地產出「看起來正常的錯誤數字」，直接污染投資決策。建議：在 pipeline 加最低限度的 sanity check（最新日期距今 ≤N 天、數值在歷史範圍 ±5σ 內、列數不暴跌），異常就發 Discord 警報而不是靜默寫入。這比任何新功能都值得先做。

### 2. 舊 Streamlit 遺留是持續性的 token 稅與誤導源
根目錄的 `app.py`、`views/`、`components/`、`api.py`、`config.py` 是遷移遺留。弱模型搜尋時會一直命中它們、甚至改錯邊（改了舊版以為修好了）。CLAUDE.md 已標注，但治本是：確認遷移完成後，問使用者能不能刪或移到 `legacy/`。每拖一個月，就多付一個月的搜尋噪音。

### 3. secrets 衛生需要一次總清理
盤點時發現 `.claude/settings.local.json` 的 permission 字串裡有明文 FRED API key（已記 LESSONS）。同模式可能存在於 shell 歷史、舊 commit、GitHub Actions log。建議使用者做一次：輪替 FRED key → 掃 repo 歷史找其他明文 key → 之後所有含 secret 的指令一律走 env var。

## 二、這套制度最可能的退化方式與預防

1. **索引斷鏈**：有人改了 `docs/agents/` 檔名或 CLAUDE.md 索引表，制度檔就變成沒人讀的死文件。→ 預防：MAINTENANCE.md §4 的季度 fresh-agent 連結檢查；任何改名必須同步索引表。
2. **LESSONS 通膨**：教訓越記越多，讀的成本超過價值，然後大家跳過不讀。→ 預防：30 條上限 + 「第二次踩才升級到常載檔」規則，嚴格執行。
3. **規則貨物崇拜**：弱模型把「派 subagent」當儀式，3 行的事也派工，反而更貴。→ 預防：MODEL_DISPATCH §1 的例外條款是制度的一部分，跟鐵律一樣重要。
4. **驗證形式化**：「驗證」退化成叫 agent 回「看過了，沒問題」。→ 預防：驗證 prompt 必含「找碴不是背書」與「引證據原文」要求（PROMPT_TEMPLATES 範本 6），沒有證據的通過不算通過。
5. **制度與現實脫節**：模型名單、工具名、外掛（cavecrew）都會變，制度檔引用它們的地方會過時。→ 預防：MODEL_DISPATCH 開頭已標「以 harness 宣告為準」；發現不一致，當下就更新 §0 並記 LESSONS。

## 三、誠實條款：這次哪些產出信心最低

1. **DIAGNOSIS.md 的「前三名」排序**（信心最低）。我只有一個 session 的觀察 + 設定檔裡的歷史痕跡，沒有跨 session 的 token 統計。排序是推斷不是量測。若實際運作發現別的漏洞更大，直接改排名，不必尊重我的版本。
2. **升降級的具體門檻**（haiku 錯 1 次升、sonnet 錯 2 次升、最多 2 輪）。這些數字是判斷後的取捨，不是實驗結果。方向我有信心（要有明確門檻、要帶失敗軌跡升級），數字本身可以按實戰調。
3. **「subagent 與主對話共用額度窗口」**：只有部分文件佐證（見 MODEL_DISPATCH §6）。若實測發現不共用，省額度的策略可以更激進。
4. **cavecrew 外掛的長期可用性**：制度多處依賴 caveman 外掛的三個 subagent。外掛若移除，MODEL_DISPATCH §1 的表要整排 fallback 到 `Explore`/`general-purpose`——表裡已寫通用型別名，但沒實測過移除後的行為。
5. **維護協議的「先問使用者」邊界**：我按保守原則劃的線（制度核心、生產環境、secrets 都要問）。Frank 若覺得太囉嗦，放寬即可——這條線的正確位置只有使用者知道。

## 四、一句話交接

制度的核心只有一件事：**貴的 context 只花在判斷，便宜的 context 花在執行，所有產出要被沒做它的人驗過。** 其他都是這句話的實作細節。

— Fable 5
