-- BamHI 拐點篩選系統 — Supabase 表結構（spec §6.3）
-- 在 Supabase Dashboard → SQL Editor 執行一次即可。

create table if not exists fundamentals_quarterly (
  cik          bigint not null,
  ticker       text,
  period_end   date not null,
  filing_date  date,            -- v1 為 NULL（Frames API 無 filed 欄位），accn 供未來反查補齊
  accn         text,
  revenue      double precision,
  net_income   double precision,
  eps_diluted  double precision,
  data_quality text,
  updated_at   timestamptz default now(),
  primary key (cik, period_end)
);

create table if not exists screen_left_pool (
  run_date       date not null,
  ticker         text not null,
  name           text,
  market_cap     double precision,
  price          double precision,
  dollar_vol_20d double precision,
  yoy_t          double precision,
  accel_t        double precision,
  accel_t1       double precision,
  margin_slope   double precision,
  eps_slope      double precision,
  flags          text,
  score          double precision,
  latest_period  date,
  filing_date    date,
  data_quality   text,
  created_at     timestamptz default now(),
  primary key (run_date, ticker)
);

create table if not exists screen_right_pool (
  run_date            date not null,
  ticker              text not null,
  name                text,
  market_cap          double precision,
  price               double precision,
  dollar_vol_20d      double precision,
  yoy_t               double precision,
  accel_t             double precision,
  accel_t1            double precision,
  margin_slope        double precision,
  eps_slope           double precision,
  flags               text,
  score               double precision,
  latest_period       date,
  filing_date         date,
  data_quality        text,
  rs_rank             double precision,
  rs_line_high        boolean,
  trend_template_pass boolean,
  weekly_pass         boolean,
  vol_confirm         boolean,
  obv_confirm         boolean,
  vcp_proxy           boolean,
  created_at          timestamptz default now(),
  primary key (run_date, ticker)
);

-- 篩選結果表允許前端（後端以 service key 讀，無需 RLS 放行 anon）
alter table fundamentals_quarterly enable row level security;
alter table screen_left_pool enable row level security;
alter table screen_right_pool enable row level security;
