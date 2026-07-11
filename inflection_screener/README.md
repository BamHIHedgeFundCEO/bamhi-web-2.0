# BamHI 拐點篩選系統（Inflection Screener）

零成本、自持資料層的美股拐點篩選。資料源僅 SEC EDGAR 官方 API + yfinance。

## 兩池架構

- **左側池（基本面拐點池）**：營收 YoY ≥ 25% 且連兩季加速（Accel > 0），獲利只看改善方向（OLS 斜率），允許為負。虧損收窄 = 改善；由負轉正 / 預計下季穿零者 🔺 置頂。
- **右側池（技術確認池）**：左側池 ∩ 週線 Stage 2 前置 ∩ 日線 Minervini 五條 ∩ RS_rank ≥ 80。

## 執行

```bash
pip install -r inflection_screener/requirements.txt

# 全量（每週六 GitHub Actions 自動跑，見 .github/workflows/screen.yml）
python -m inflection_screener.src.main

# Dry-run 核對（驗收 #2）：印 8 季營收序列，跳過 Discord/Supabase
python -m inflection_screener.src.main --tickers NVDA,AAPL,CVNA,SOUN,COST --dry-run

# 測試
python -m pytest inflection_screener/tests -q
```

## 環境變數

| 變數 | 必要 | 說明 |
|------|------|------|
| `EDGAR_UA` | ✅ | SEC 要求的 User-Agent，格式 `BamHI Research you@email`，缺失 403 |
| `SUPABASE_URL` | 入庫用 | Supabase 專案 URL |
| `SUPABASE_SERVICE_KEY`（或 `SUPABASE_KEY`） | 入庫用 | service role key |
| `DISCORD_WEBHOOK_URL` | 推送用 | Discord webhook（失敗不中斷 pipeline） |

首次使用前在 Supabase SQL Editor 執行 `supabase_schema.sql` 建三張表。

## 資料流

EDGAR Frames（~40 calls，全市場批量）→ 清洗（tag coalesce / Q4=FY−3Q 推導 / 去重）
→ 指標（YoY、Accel 二階、margin/EPS OLS 斜率、翻正旗標）→ 閘門②營收加速
→ yfinance（僅通過者逐檔 + SPY）→ 閘門①流動性 → 左側池 → 週線+日線模板+RS → 右側池
→ CSV / Discord / Supabase（`run_date` 保留歷史，upsert 冪等）。

## 合規與硬性約束

- EDGAR 限速 ≤ 8 req/sec（每 request sleep 0.15s），回應本地快取 24h（`cache/edgar/`）。
- yfinance 絕不全市場掃，僅對基本面通過者逐檔；單檔失敗記 log 跳過。
- 淨利 / EPS 禁用 YoY% （負值變號會錯亂），一律用 level/margin 斜率。
- 非日曆財年公司：v1 標記 `data_quality='partial'` 排除於加速度計算。

## v1 已知偏離（與使用者確認過）

1. **filing_date 為 NULL**：EDGAR Frames API 回應不含 `filed` 欄位（SEC 已在伺服端每季每公司選一筆）。表仍建 `filing_date` 欄位，另存 `accn` + `updated_at`，未來可用 accn 反查 submissions 補齊後做 point-in-time 回測。
2. **突破日定義**（vol_confirm）：近 20 個交易日內、收盤創 63 日新高的最近一日。

## 前端整合

- 後端：`backend/routers/inflection.py` + `backend/services/inflection.py`（讀 Supabase）
- 前端：`/app/inflection` → `frontend/src/views/InflectionView.vue`
