-- dual_pool_institution.sql — institution_quarterly 表（§6.9）
--
-- 機構持倉季度索引：13F bulk 資料集反向建 ticker→新進機構數
-- 由 data_pipeline/dual_pool/institution_13f.py 季度 job 寫入
-- RLS：service_role 全存取，anon 禁讀（前端透過 FastAPI backend 查）

CREATE TABLE IF NOT EXISTS institution_quarterly (
  ticker        TEXT         NOT NULL,
  quarter       TEXT         NOT NULL,  -- 格式 'YYYY-QN'，如 '2025-Q1'
  new_holders   INT          NOT NULL DEFAULT 0,
    -- 本季新進機構 filer 數（上季無持倉、本季有；首次跑時 = total_holders）
  total_holders INT          NOT NULL DEFAULT 0,
    -- 本季總機構 filer 數（持有該 ticker 的唯一 filer CIK 數）
  known_at      TIMESTAMPTZ  NOT NULL,
    -- 系統實跑時點（point-in-time；非 PERIODOFREPORT，§8.2）
  PRIMARY KEY (ticker, quarter)
);

-- RLS
ALTER TABLE institution_quarterly ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON institution_quarterly
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- scoring query index（按 ticker 取最新季）
CREATE INDEX IF NOT EXISTS idx_institution_quarterly_ticker
  ON institution_quarterly (ticker, quarter DESC);


-- ── cusip_map — CUSIP→ticker 對映持久化 ──────────────────────────────
-- Render 檔案系統每次部署歸零，本地 JSON cache 會消失 → 每次 13F 全量重查 OpenFIGI。
-- 此表跨部署持久：首次全量查一次後，之後只補 cache miss。
-- ticker 可 NULL（OpenFIGI 查無結果也記錄，避免重複查同一個查不到的 CUSIP）。

CREATE TABLE IF NOT EXISTS cusip_map (
  cusip      TEXT         PRIMARY KEY,
  ticker     TEXT,
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

ALTER TABLE cusip_map ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON cusip_map
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
