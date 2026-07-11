"""BamHI 拐點篩選系統 — 全部門檻常數集中於此（spec §5.2 要求）。

調參只改這裡，不要把常數散進各模組。
"""
import os

# ── EDGAR（spec §2.1 / §2.2 不可妥協）──
EDGAR_FRAMES_URL = "https://data.sec.gov/api/xbrl/frames/us-gaap/{concept}/{unit}/{frame}.json"
EDGAR_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_UA_ENV = "EDGAR_UA"          # User-Agent："BamHI Research contact@email"
EDGAR_SLEEP_SEC = 0.15             # ≤ 8 req/sec（官方上限 10，保守抓 8）
EDGAR_CACHE_DIR = os.path.join("cache", "edgar")
EDGAR_CACHE_TTL_HOURS = 24
# 判定「當季已普遍申報」的最低 frame 列數，低於此回退一季
EDGAR_MIN_FRAME_ROWS = 1000

# 營收 tag coalesce 優先序（spec §3.1）
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",  # ASC 606，覆蓋最廣
    "Revenues",
    "SalesRevenueNet",
]
NET_INCOME_CONCEPT = "NetIncomeLoss"
EPS_CONCEPT = "EarningsPerShareDiluted"
EPS_UNIT = "USD-per-shares"
USD_UNIT = "USD"

N_QUARTERS = 8                     # 抓取最近 8 個日曆季
MIN_QUARTERS_FOR_ACCEL = 7         # 連兩季 Accel 至少需 7 季有效數據
PARTIAL_MISSING_THRESHOLD = 2      # 缺 ≥ 2 季 → data_quality='partial'（spec §3.4）

# ── 閘門 ①：流動性 / 規模（spec §5.1）──
MIN_MARKET_CAP = 100_000_000       # USD
MIN_PRICE = 3.0                    # USD
MIN_DOLLAR_VOL_20D = 30_000_000    # mean(close×volume, 20d) USD

# ── 閘門 ②：營收加速（spec §5.2）──
YOY_MIN = 0.25                     # YoY_t >= 25%
ACCEL_CONSEC_QUARTERS = 2          # 連兩季 Accel > 0

# ── 排序分數權重（spec §5.3）──
SCORE_W_MARGIN_SLOPE = 0.5
SCORE_W_EPS_SLOPE = 0.3
SCORE_W_ACCEL = 0.2

# ── 右側池技術參數（spec §5.4）──
PRICE_LOOKBACK_DAYS = 500          # 日曆天數；供 MA200 + 20 日斜率 + 週線 MA30
WEEKLY_MA_FAST = 10
WEEKLY_MA_SLOW = 30
WEEKLY_SLOPE_WEEKS = 5
DAILY_MA = (50, 150, 200)
MA200_RISING_DAYS = 20
LOW_52W_MULT = 1.30
HIGH_52W_MULT = 0.75
RS_WEIGHTS = {63: 0.4, 126: 0.3, 189: 0.2, 252: 0.1}
RS_RANK_MIN = 80                   # 百分位硬閘門
RS_LINE_HIGH_DAYS = 126
VOL_CONFIRM_MULT = 1.5
VOL_AVG_DAYS = 50
BREAKOUT_LOOKBACK_DAYS = 20        # 近 20 日內找突破日（使用者選定義）
BREAKOUT_HIGH_DAYS = 63            # 突破 = 收盤創 63 日新高
OBV_MA_DAYS = 20
OBV_HIGH_DAYS = 63
VCP_ATR_DAYS = 14
VCP_LOOKBACK_DAYS = 60
VCP_CONTRACTION_MIN = 0.30

BENCHMARK = "SPY"
YF_RETRIES = 3                     # yfinance retry（指數退避）

# ── 輸出 ──
OUTPUT_DIR = "output"
DISCORD_WEBHOOK_ENV = "DISCORD_WEBHOOK_URL"
SUPABASE_URL_ENV = "SUPABASE_URL"
# 相容兩種命名：repo 既有 SUPABASE_SERVICE_KEY，spec 寫 SUPABASE_KEY
SUPABASE_KEY_ENVS = ("SUPABASE_SERVICE_KEY", "SUPABASE_KEY")
TABLE_FUNDAMENTALS = "fundamentals_quarterly"
TABLE_LEFT = "screen_left_pool"
TABLE_RIGHT = "screen_right_pool"
