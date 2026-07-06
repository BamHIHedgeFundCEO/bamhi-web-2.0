-- dual_pool_scores.sql — 階段 3 建表 DDL
-- 貼進 Supabase SQL editor 執行一次即可
-- 對應 §3.3 scores schema + gate_passed + data_gaps

-- ──────────────────────────────────────────────────────────────────────
-- scores（L3 輸出，每日快照，§3.3）
-- PK = (ticker, score_date)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scores (
    ticker        TEXT    NOT NULL,
    score_date    DATE    NOT NULL,
    side          TEXT    NOT NULL CHECK (side IN ('left', 'right')),

    -- 加權總分（0-100）
    total         NUMERIC NOT NULL DEFAULT 0,

    -- 六因子分（各 0-1）
    catalyst      NUMERIC NOT NULL DEFAULT 0,
    institution   NUMERIC NOT NULL DEFAULT 0,   -- stage 5 前恆 0（§12）
    op_leverage   NUMERIC NOT NULL DEFAULT 0,
    partnership   NUMERIC NOT NULL DEFAULT 0,
    insider       NUMERIC NOT NULL DEFAULT 0,
    narrative     NUMERIC NOT NULL DEFAULT 0,

    -- [v1.1] 催化劑 Gate 結果（§7.4）— 顯示層過濾，不影響 watchpool 成員資格
    -- true = 過 Gate（前端「候選清單」區）；false = 池內觀察區
    gate_passed   BOOLEAN NOT NULL DEFAULT false,

    -- 一票否決旗標（integrity/dilution/cash_runway/liquidity/guidance_missed）
    -- 非空 = 前端標紅，分數照算
    veto_flags    TEXT[]  NOT NULL DEFAULT '{}',

    -- 資料缺失標記（data_gap:institution / data_gap:op_leverage / data_gap:cash_runway 等）
    data_gaps     TEXT[]  NOT NULL DEFAULT '{}',

    PRIMARY KEY (ticker, score_date)
);

-- 加速查詢
CREATE INDEX IF NOT EXISTS scores_score_date_idx ON scores (score_date DESC);
CREATE INDEX IF NOT EXISTS scores_side_idx       ON scores (side);
CREATE INDEX IF NOT EXISTS scores_gate_idx       ON scores (gate_passed);
CREATE INDEX IF NOT EXISTS scores_ticker_idx     ON scores (ticker);

-- ──────────────────────────────────────────────────────────────────────
-- Row Level Security
-- service_role 已預設有完整權限；anon 唯讀（前端走 FastAPI，不直連）
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon_read_scores"
    ON scores FOR SELECT
    TO anon
    USING (true);
