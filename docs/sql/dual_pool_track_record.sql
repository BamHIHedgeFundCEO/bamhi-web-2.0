-- dual_pool_track_record.sql — track_record 表（§3.4 + v1.1 verify_method）
--
-- guidance/commitment 事件兌現率追蹤
-- 由 run_stage2.py 寫入（promise），由 verify_track_record.py 每週更新（verified）
-- RLS：service_role 全存取，anon 禁讀

CREATE TABLE IF NOT EXISTS track_record (
  id               BIGSERIAL    PRIMARY KEY,
  ticker           TEXT         NOT NULL,
  promise_date     DATE         NOT NULL,  -- 事件發生日（8-K 申報日）
  promise_text     TEXT         NOT NULL,  -- 承諾摘要（headline，≤20字）
  promise_deadline DATE         NOT NULL,  -- 兌現截止日（timeline_months 推算，無則+90天）
  verified         BOOLEAN,               -- NULL=待核；true=兌現；false=未兌現
  verify_date      DATE,                  -- 驗證日期
  verify_method    TEXT,                  -- 'llm' | 'manual'
  verify_attempts  INT          NOT NULL DEFAULT 0,
    -- LLM 判定 unknown 次數；≥2 次 → 進人工佇列（verify_method='manual'）
  UNIQUE (ticker, promise_date, promise_text)
);

-- RLS
ALTER TABLE track_record ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON track_record
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- verify job query index（掃到期未核 promise）
CREATE INDEX IF NOT EXISTS idx_track_record_deadline_unverified
  ON track_record (promise_deadline)
  WHERE verified IS NULL;

-- scoring query index（按 ticker 取兌現率）
CREATE INDEX IF NOT EXISTS idx_track_record_ticker
  ON track_record (ticker);
