-- dual_pool_processed.sql — edgar_processed 建表 DDL
-- 持久化已處理的 EDGAR accession number，解決 Render 暫態檔案系統問題
-- （每次部署歸零 → stage2 重回補 90 天；改用 Supabase 後跨部署持久）
-- 貼進 Supabase SQL editor 執行一次即可

CREATE TABLE IF NOT EXISTS edgar_processed (
    accession_no   TEXT        PRIMARY KEY,          -- EDGAR accession，如 0001819774-24-000021
    processed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW() -- 首次處理時間（審計用）
);

-- ──────────────────────────────────────────────────────────────────────
-- Row Level Security（照 dual_pool_events.sql 風格）
-- service key 寫入，anon key 唯讀（前端走 FastAPI，不直連 anon key）
-- ──────────────────────────────────────────────────────────────────────
ALTER TABLE edgar_processed ENABLE ROW LEVEL SECURITY;

-- service_role 擁有完整權限（已預設），只加 anon 唯讀 policy
CREATE POLICY "anon_read_edgar_processed"
    ON edgar_processed FOR SELECT
    TO anon
    USING (true);
