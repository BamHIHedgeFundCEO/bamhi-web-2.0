# 快速診斷：此環境最漏 token、最易失焦、最易出錯的三件事

> 寫給接手的模型（Sonnet / Opus / Haiku）。每條附「怎麼判斷你正在犯」與「照做即可的修法」。
> 本檔是其他制度檔的依據；改制度前先讀這裡。

---

## 第 1 名（漏 token）：主對話直接讀大檔 / 大輸出

**此 repo 的具體地雷**：
- `data/*.csv`（每日戰報，數千列）、`data/insider_cache.json`、`*.xlsx`（羅素1000/2000/3000）
- `.claude/settings.local.json`（97 條 permission，約 100 行）
- `gh run view --log`（CI log 動輒數百行）
- 前端 `npm run build` / pipeline script 的完整輸出

**怎麼判斷你正在犯**：你即將用 Read/cat 開一個超過 200 行的檔，而你只需要其中幾行或一個結論。

**修法（照做）**：
1. 只要「結論」不要「內容」→ 派 `caveman:cavecrew-investigator`（找位置）或 `Explore`（廣搜），指定 `model: haiku`。
2. 必須自己讀 → `Read` 加 `offset`/`limit`，或 `Grep` 帶 `-C 3` 只取命中段。
3. CSV/xlsx 一律不進主對話：用 `python -c "import pandas as pd; df=pd.read_csv(...); print(df.shape, df.columns.tolist()); print(df.head(3))"` 只看形狀與樣本。
4. CI log 用 `Select-String -Pattern "關鍵字" | Select-Object -First 10`（見 settings.local.json 內既有慣例）。

---

## 第 2 名（易出錯）：Windows 雙 shell + 編碼

**現象**：同一台機器有 PowerShell 5.1 與 Git Bash 兩套語法；中文檔名（`羅素3000.xlsx`）、中文 log、UTF-16 預設編碼，會造成指令連錯 3-4 次、每次重試都燒 token 且讓對話偏題。

**怎麼判斷你正在犯**：同一個指令你已經改寫重試第 2 次，錯誤訊息是語法錯誤（`&&` 不能用、here-string 解析失敗）或亂碼/UnicodeEncodeError。

**修法（照做）**：
1. Python 相關一律先設 `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"`（PowerShell）。
2. PowerShell 5.1 沒有 `&&`、`||`、`?:`、`??` — 用 `A; if ($?) { B }`。POSIX 語法（管線、grep、heredoc）改用 Bash 工具跑。
3. 系統 `python` 是壞捷徑：用 `C:\Users\User\anaconda3\python.exe` 或 `conda run`（見記憶 python-env.md）。
4. PowerShell 寫檔給其他工具讀時必加 `-Encoding utf8`。
5. **兩次規則**：同一指令改寫失敗 2 次 → 停止重試，換方法（換 shell、寫成 `_verify_*.py` 臨時腳本跑、或把問題縮小）。換方法後仍失敗 → 走 [MODEL_DISPATCH.md](MODEL_DISPATCH.md) §4 升降級，不要第 3 次原地重試。

---

## 第 3 名（易失焦）：長 session 的重試迴圈與目標漂移

**現象**：修 A 時發現 B 壞了，跑去修 B 又發現 C；或對同一個失敗（部署、CI、爬蟲）反覆重跑等待；session 被 compact 後忘記原始目標。

**怎麼判斷你正在犯**：你已經連續 3 個以上工具呼叫沒有產生「可存檔的進度」（新增/修改了一個檔案、得到一個可回報的確定結論、或完成一個子任務，三者都不算就是沒進度）；或你正在做的事無法用一句話連回使用者的原始請求。

**修法（照做）**：
1. **隨做隨存**：每完成一個可交付單位立即寫檔/commit（使用者要求時），不要攢到最後。
2. 發現順手可修的旁支問題 → 不修，記一行到回報裡（「另發現 X，未處理」），回到主線。
3. 等待外部狀態（CI、Render 部署）→ 用背景執行或 `gh run watch`，不要輪詢式 sleep。
4. 同一件事（含換方法）總計重試 2 輪仍失敗 → 停下，向使用者回報失敗軌跡（做了什麼、錯誤原文、你的假設），見 [JUDGMENT_RUBRICS.md](JUDGMENT_RUBRICS.md) 的「何時停下來問」。

---

## 附註

- caveman mode hook 常駐（壓縮回覆輸出），cavecrew subagent 的回傳也是壓縮格式 — 這是刻意設計，省的是「進主對話的 token」。
- gitStatus 是 session 開始時的快照，不會自動更新；動 git 前先重跑 `git status`。
- 機器人 commit（訊息含 `[skip ci]` 或 Genesis Bot）會頻繁改 `data/`，pull 前先 stash 或確認工作區乾淨。
