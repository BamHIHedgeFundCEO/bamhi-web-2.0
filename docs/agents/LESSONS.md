# 踩雷教訓（LESSONS）

> 追加式日誌。格式與升級規則見 [MAINTENANCE.md](MAINTENANCE.md) §2。上限 30 條，超過先精簡。

## 2026-07-04 系統 python 是壞捷徑
- 情境：任何要跑 Python 的時刻
- 雷：`python` 指令指向壞的 Windows Store 捷徑
- 修法：用 `C:\Users\User\anaconda3\python.exe` 或 `conda run`
- 影響檔案：（全域）已寫入 CLAUDE.md 與記憶 python-env.md

## 2026-07-04 PowerShell 5.1 語法陷阱
- 情境：在 PowerShell 工具跑指令
- 雷：`&&`/`||` 是 parser error；native exe 加 `2>&1` 會誤報失敗；預設編碼 UTF-16
- 修法：`A; if ($?) { B }`；不重導 stderr；寫檔加 `-Encoding utf8`；POSIX 語法改用 Bash 工具
- 影響檔案：（全域）已寫入 DIAGNOSIS.md 第 2 名

## 2026-07-04 中文輸出炸 UnicodeEncodeError
- 情境：跑 pipeline / 後端腳本，log 含中文
- 雷：cp950 編碼錯誤中斷腳本
- 修法：先設 `$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"` 再跑
- 影響檔案：（全域）已寫入 CLAUDE.md 開發環境區

## 2026-07-04 FMP key 曾硬編碼進 git（已修，key 待輪替）
- 情境：secrets 總盤點
- 雷：`data_engine/equity.py` 硬編碼 FMP key，進了 HEAD + 4 個歷史 commit；先前 commit `1bf6f63` 只清了 backend 那份，漏了這份
- 修法：任何 key 一律 `os.getenv()`；「清 key」要全 repo grep 該值，不能只修被回報的那個檔；歷史殘留靠輪替解決，filter-repo 為選配
- 影響檔案：`legacy/data_engine/equity.py`（已修為 env var）

## 2026-07-04 settings.local.json 允許清單含明文 API key
- 情境：盤點 `.claude/settings.local.json`
- 雷：permission 字串裡殘留 FRED_API_KEY 明文（歷史指令被存成允許規則）
- 修法：含 secret 的指令改用 `$env:FRED_API_KEY` 引用、不要讓含明文 key 的指令進允許清單；已存在的請使用者手動清理並考慮輪替 key
- 影響檔案：`.claude/settings.local.json`

## 2026-07-05 yfinance MultiIndex 欄位：本機煙霧測試過、CI 全滅
- 情境：dual_pool 階段 1 首次 GitHub Actions 實跑，1166 檔全部 side='error'，workflow 卻顯示 success
- 雷：三連環——(1) yfinance 1.2 單檔 download 回 MultiIndex 欄位，`hist["Close"]` 變 DataFrame；(2) 本機舊 pandas 對 `float(單元素Series)` 只警告、CI 新 pandas 直接 TypeError，被 except 吞成靜默 error；(3) 修復後舊 cache 仍存著 MultiIndex 欄位，增量 concat 再炸一次
- 修法：外部資料源的欄位形狀在「邊界處正規化」（下載點+cache 讀取點+消費端三處攤平）；煙霧測試要走「冷 cache + 真實下載」路徑，暖 cache 會遮蔽下載格式問題；批次 job 的驗收不能只看 exit code，要看產出計數（left/right/discard 全 0 = 紅旗）
- 影響檔案：`data_pipeline/dual_pool/run_stage1.py`、`l1_features.py`
