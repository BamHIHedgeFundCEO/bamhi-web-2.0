"""技術層單元測試：趨勢模板邊界條件（spec §7）。"""
import numpy as np
import pandas as pd

from inflection_screener.src import technicals


def _ohlcv(closes) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-02", periods=len(closes))
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({
        "Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c,
        "Volume": np.full(len(c), 1_000_000.0),
    }, index=idx)


def _uptrend(n=320, start=100.0, end=200.0):
    return _ohlcv(np.linspace(start, end, n))


class TestDailyTemplate:
    def test_steady_uptrend_passes(self):
        assert technicals.daily_template_pass(_uptrend())

    def test_downtrend_fails(self):
        assert not technicals.daily_template_pass(_ohlcv(np.linspace(200, 100, 320)))

    def test_deep_pullback_fails_d5(self):
        """漲後急跌 30%（跌破 52 週高 × 0.75）→ D5 擋下。"""
        closes = np.concatenate([np.linspace(100, 200, 300), np.full(20, 138.0)])
        assert not technicals.daily_template_pass(_ohlcv(closes))

    def test_insufficient_history_fails(self):
        assert not technicals.daily_template_pass(_uptrend(n=150))

    def test_flat_ma200_boundary(self):
        """完全水平序列：MA200_t == MA200_{t-20}，D2（嚴格 >）必須擋下。"""
        assert not technicals.daily_template_pass(_ohlcv(np.full(320, 100.0)))


class TestWeekly:
    def test_uptrend_passes(self):
        assert technicals.weekly_pass(_uptrend())

    def test_downtrend_fails(self):
        assert not technicals.weekly_pass(_ohlcv(np.linspace(200, 100, 320)))


class TestRS:
    def test_outperformer_positive_rs(self):
        stock = _uptrend()  # +100%
        spy = pd.Series(np.full(320, 100.0), index=stock.index)
        assert technicals.rs_raw(stock["Close"], spy) > 0

    def test_underperformer_negative_rs(self):
        stock = _ohlcv(np.linspace(100, 80, 320))
        spy = pd.Series(np.linspace(100, 120, 320), index=stock.index)
        assert technicals.rs_raw(stock["Close"], spy) < 0

    def test_rs_line_lead_flag(self):
        """股價未創 126 日新高、但 RS Line（÷SPY）創新高 → 🔺 flag。"""
        n = 320
        idx = pd.bdate_range("2024-01-02", periods=n)
        # 股價先衝高 120 再緩跌至 100（未創新高）
        close = pd.Series(np.concatenate([np.linspace(100, 120, 60), np.linspace(110, 100, n - 60)]), index=idx)
        # SPY 持續下跌 → 比值持續創新高
        spy = pd.Series(np.linspace(100, 60, n), index=idx)
        assert technicals.rs_line_lead_flag(close, spy)

    def test_no_flag_when_price_also_high(self):
        stock = _uptrend()
        spy = pd.Series(np.full(320, 100.0), index=stock.index)
        assert not technicals.rs_line_lead_flag(stock["Close"], spy)


class TestVolumeAnnotations:
    def test_vcp_contraction_detected(self):
        """前段高波動、近段低波動 → vcp_proxy True。"""
        n = 320
        idx = pd.bdate_range("2024-01-02", periods=n)
        rng = np.random.default_rng(42)
        base = np.full(n, 100.0)
        noise = np.concatenate([rng.normal(0, 8, n - 60), rng.normal(0, 0.5, 60)])
        c = pd.Series(base + noise, index=idx)
        spread = np.concatenate([np.full(n - 60, 10.0), np.full(60, 0.5)])
        df = pd.DataFrame({
            "Open": c, "High": c + spread / 2, "Low": c - spread / 2, "Close": c,
            "Volume": np.full(n, 1_000_000.0),
        }, index=idx)
        assert technicals.volume_annotations(df)["vcp_proxy"]

    def test_breakout_volume_confirm(self):
        """最後一日創 63 日新高且爆量 2 倍 → vol_confirm True。"""
        n = 320
        closes = np.concatenate([np.linspace(100, 150, n - 1), [160.0]])
        df = _ohlcv(closes)
        df.iloc[-1, df.columns.get_loc("Volume")] = 2_000_000.0
        assert technicals.volume_annotations(df)["vol_confirm"]
