-- dual_pool_job_state: 長時任務跨 Render 重啟持久的執行狀態
-- PK = job_type（'13f' / 'stage2' / 'verify' 等）
-- heartbeat_at 由 Render 背景執行緒每 5 分鐘更新；
-- 若 status='running' 且 heartbeat_at 超過 15 分鐘未更新
-- → backend 回傳 status='interrupted'（process 已死，可重觸）

CREATE TABLE IF NOT EXISTS dual_pool_job_state (
  job_type      TEXT         PRIMARY KEY,
  status        TEXT         NOT NULL DEFAULT 'never_run',
  started_at    TIMESTAMPTZ,
  finished_at   TIMESTAMPTZ,
  heartbeat_at  TIMESTAMPTZ,
  quarter       TEXT,
  result        JSONB,
  error         TEXT,
  updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

ALTER TABLE dual_pool_job_state ENABLE ROW LEVEL SECURITY;

-- service_role（backend 使用的 key）全權存取
CREATE POLICY "service_role_all" ON dual_pool_job_state
  FOR ALL TO service_role USING (true) WITH CHECK (true);
