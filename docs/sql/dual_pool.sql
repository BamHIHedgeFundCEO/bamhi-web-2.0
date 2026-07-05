-- dual_pool.sql — 階段 1 建表 DDL
-- 貼進 Supabase SQL editor 執行一次即可
-- 只含 watchpool + universe_snapshot（§3.1 / §3.5）

-- ──────────────────────────────────────────────────────────────────────
-- watchpool（L1 輸出，§3.1）
-- PK = ticker（每檔只存最新狀態）
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchpool (
    ticker        TEXT        PRIMARY KEY,
    side          TEXT        NOT NULL CHECK (side IN ('left', 'right')),
    market        TEXT        NOT NULL DEFAULT 'US',
    market_cap    NUMERIC,
    entangle      NUMERIC,    -- 長均線糾纏度
    slope200      NUMERIC,    -- MA200 近 20 日斜率
    dist_low      NUMERIC,    -- 距 52 週低比例
    adv_dollar    NUMERIC,    -- 20 日均成交額（$）
    liquidity_ok  BOOLEAN,    -- 是否達流動性底線 $2M
    low_adv_streak INT        NOT NULL DEFAULT 0,  -- 連續 adv<$2M 交易日數（§5.6 rolling counter，連 5 日→移出）
    status        TEXT        NOT NULL DEFAULT 'active'
                              CHECK (status IN ('active', 'cooldown')),
                              -- 軟刪除：移出時標 'cooldown' 不刪列，供 §5.6 冷卻 5 交易日檢查；
                              -- 讀取端（前端/回測）只取 status='active'
    removed_at    DATE,       -- 移出日（status='cooldown' 時有值）；冷卻期滿且未重進由管線清列
    entered_at    DATE        NOT NULL,   -- 進池日（遲滯機制用，§5.6）
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 加速查詢
CREATE INDEX IF NOT EXISTS watchpool_side_idx ON watchpool (side);
CREATE INDEX IF NOT EXISTS watchpool_entered_at_idx ON watchpool (entered_at);
CREATE INDEX IF NOT EXISTS watchpool_status_idx ON watchpool (status);

-- ──────────────────────────────────────────────────────────────────────
-- universe_snapshot（L0 每日快照，§3.5，回測 forward-test 用）
-- PK = (snapshot_date, ticker)
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS universe_snapshot (
    snapshot_date DATE    NOT NULL,
    ticker        TEXT    NOT NULL,
    market_cap    NUMERIC,
    adv_dollar    NUMERIC,
    close         NUMERIC,
    PRIMARY KEY (snapshot_date, ticker)
);

-- 加速按日期查詢
CREATE INDEX IF NOT EXISTS universe_snapshot_date_idx ON universe_snapshot (snapshot_date);

-- ──────────────────────────────────────────────────────────────────────
-- Row Level Security（Supabase 建議）
-- service key 寫入，anon key 唯讀（前端走 FastAPI，不直連 anon key）
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE watchpool          ENABLE ROW LEVEL SECURITY;
ALTER TABLE universe_snapshot  ENABLE ROW LEVEL SECURITY;

-- service_role 擁有完整權限（已預設），此處只加 anon 唯讀 policy
CREATE POLICY "anon_read_watchpool"
    ON watchpool FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "anon_read_universe_snapshot"
    ON universe_snapshot FOR SELECT
    TO anon
    USING (true);
