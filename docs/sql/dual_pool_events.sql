-- dual_pool_events.sql — 階段 2 建表 DDL
-- 貼進 Supabase SQL editor 執行一次即可
-- events 表（L2 催化劑抽取輸出，§3.2）

-- ──────────────────────────────────────────────────────────────────────
-- events（L2 輸出，§3.2）
--
-- 冪等鍵設計（§8.1 防重複）：
--   accession_no  — EDGAR 申報識別碼（格式 XXXXXXXXXX-YY-ZZZZZZ），
--                   唯一識別一份申報文件；同公司同日可有多份不同 8-K，
--                   以 accession_no 而非 (ticker, event_date, event_type) 為鍵
--                   才能精確去重（後者在同日多份申報時衝突）。
--   seq_in_filing — 同一申報件內第 N 個事件（0-indexed）；一份 8-K 可含多事件。
--   重跑同一申報 → 產出相同 (accession_no, seq_in_filing) → ON CONFLICT DO NOTHING，
--   不得重複寫入（§8.1 冪等要求）。
-- ──────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    id                 BIGSERIAL    PRIMARY KEY,

    -- 冪等鍵（§8.1）
    accession_no       TEXT        NOT NULL,  -- EDGAR accession，如 0001819774-24-000021
    seq_in_filing      SMALLINT    NOT NULL DEFAULT 0,  -- 同申報件第 N 個事件（0-indexed）

    ticker             TEXT        NOT NULL,
    event_date         DATE        NOT NULL,
    known_at           TIMESTAMPTZ NOT NULL,  -- 系統得知時間（point-in-time 核心，§8.2）
    source             TEXT        NOT NULL,  -- '8-K' | 'PR' | 'Form4'
    source_url         TEXT,
    event_type         TEXT        NOT NULL,  -- 見 §6.4 枚舉
    headline           TEXT        NOT NULL,  -- 中立一句話 ≤20 字，繁體中文
    counterparty       TEXT,
    counterparty_tier  TEXT        CHECK (counterparty_tier IN ('tier1_giant', 'tier2', 'unknown')),
    magnitude_usd      NUMERIC,
    magnitude_pct_rev  NUMERIC,
    timeline_months    INT,
    is_recurring       BOOLEAN     NOT NULL DEFAULT false,
    specificity        SMALLINT    NOT NULL CHECK (specificity BETWEEN 1 AND 5),
    direction          TEXT        NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    is_integrity_flag  BOOLEAN     NOT NULL DEFAULT false,
    is_dilution_flag   BOOLEAN     NOT NULL DEFAULT false,
    evidence_anchor    TEXT,  -- ≤15 字逐字錨句（原文語言），審計用
    extraction_method  TEXT        NOT NULL CHECK (extraction_method IN ('llm', 'rule')),

    -- 防重複約束（§8.1 冪等核心）
    UNIQUE (accession_no, seq_in_filing)
);

-- 加速常用查詢
CREATE INDEX IF NOT EXISTS events_ticker_idx      ON events (ticker);
CREATE INDEX IF NOT EXISTS events_known_at_idx    ON events (known_at);
CREATE INDEX IF NOT EXISTS events_event_date_idx  ON events (event_date);
CREATE INDEX IF NOT EXISTS events_direction_idx   ON events (direction);
CREATE INDEX IF NOT EXISTS events_accession_idx   ON events (accession_no);

-- ──────────────────────────────────────────────────────────────────────
-- Row Level Security（照 dual_pool.sql 風格）
-- service key 寫入，anon key 唯讀（前端走 FastAPI，不直連 anon key）
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- service_role 擁有完整權限（已預設），此處只加 anon 唯讀 policy
CREATE POLICY "anon_read_events"
    ON events FOR SELECT
    TO anon
    USING (true);
