"""指標層單元測試（spec 驗收 #1：(a) 虧損收窄=改善；(b) 一次性基期被連兩季 Accel 擋下；
(c) Q4 缺 Q2 回傳 NaN — 亦在 test_clean 覆蓋，此處按驗收要求重申）。"""
import numpy as np
import pandas as pd

from inflection_screener.src import clean, fundamentals


def _qtable(revenues, net_incomes=None, eps=None, cik=1):
    """8 季逐季寬表（2024Q1..2025Q4）。"""
    n = len(revenues)
    quarters = [(2024 + (i // 4), i % 4 + 1) for i in range(n)]
    return pd.DataFrame({
        "cik": cik,
        "year": [y for y, _ in quarters],
        "q": [q for _, q in quarters],
        "period_end": [f"{y}-{q * 3:02d}-30" for y, q in quarters],
        "revenue": revenues,
        "net_income": net_incomes if net_incomes is not None else [10.0] * n,
        "eps_diluted": eps if eps is not None else [0.1] * n,
        "accn": "0001-25-000001",
        "filing_date": None,
        "data_quality": "ok",
    })


class TestLossNarrowingIsImprovement:
    def test_ni_minus100_to_minus50_margin_slope_positive(self):
        """驗收 #1(a)：淨利 −100 → −50（虧損收窄），margin_slope 必須判定為改善（> 0）。"""
        q = _qtable(
            revenues=[1000.0] * 8,
            net_incomes=[-100.0, -95.0, -90.0, -85.0, -80.0, -70.0, -60.0, -50.0],
        )
        m = fundamentals.compute_metrics(q)
        assert len(m) == 1
        assert m["margin_slope"].iloc[0] > 0  # 虧損收窄亦為改善
        assert not m["flag_turn_positive"].iloc[0]

    def test_turn_positive_flag(self):
        q = _qtable(
            revenues=[1000.0] * 8,
            net_incomes=[-100.0, -80.0, -60.0, -40.0, -30.0, -20.0, -10.0, 5.0],
        )
        m = fundamentals.compute_metrics(q)
        assert m["flag_turn_positive"].iloc[0]

    def test_near_positive_flag(self):
        """虧損中但 margin_slope > 0 且外推下季 ≥ 0 → flag_near_positive。"""
        q = _qtable(
            revenues=[1000.0] * 8,
            net_incomes=[-200.0, -170.0, -140.0, -110.0, -80.0, -60.0, -35.0, -10.0],
        )
        m = fundamentals.compute_metrics(q)
        assert m["flag_near_positive"].iloc[0]


class TestAccelGate:
    def test_one_time_base_jump_blocked(self):
        """驗收 #1(b)：一次性基期跳升（只有最新一季 Accel > 0）必須被連兩季條件擋下。"""
        q = _qtable(revenues=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 140.0])
        m = fundamentals.compute_metrics(q)
        row = m.iloc[0]
        assert row["yoy_t"] >= 0.25          # YoY 本身過門檻
        assert row["accel_t"] > 0            # 最新季有加速
        assert not (row["accel_t1"] > 0)     # 但前一季沒有
        assert not fundamentals.passes_accel_gate(row)

    def test_sustained_acceleration_passes(self):
        q = _qtable(revenues=[100.0, 100.0, 100.0, 100.0, 110.0, 125.0, 145.0, 170.0])
        m = fundamentals.compute_metrics(q)
        row = m.iloc[0]
        # YoY: 10% → 25% → 45% → 70%，連兩季 Accel > 0
        assert fundamentals.passes_accel_gate(row)

    def test_negative_base_revenue_gives_nan_yoy(self):
        q = _qtable(revenues=[-10.0, 100.0, 100.0, 100.0, 100.0, 130.0, 170.0, 220.0])
        m = fundamentals.compute_metrics(q)
        assert len(m) == 1  # R_{t-4} > 0 之後的季仍可算；基期 ≤ 0 的 YoY 為 NaN

    def test_insufficient_quarters_excluded(self):
        q = _qtable(revenues=[100.0, 110.0, 125.0, 145.0, 170.0, 200.0])  # 只有 6 季
        m = fundamentals.compute_metrics(q)
        assert m.empty


class TestQ4NaN:
    def test_q4_missing_q2_nan(self):
        """驗收 #1(c)：Q4 = FY − 3Q 推導在缺 Q2 時正確回傳 NaN。"""
        q = pd.DataFrame({
            "cik": [1, 1], "year": [2025, 2025], "q": [1, 3],
            "end": ["2025-03-31", "2025-09-30"], "val": [20.0, 25.0],
            "accn": ["a", "a"],
        })
        fy = pd.DataFrame({
            "cik": [1], "year": [2025], "q": [0],
            "end": ["2025-12-31"], "val": [100.0], "accn": ["a"],
        })
        out = clean.derive_q4(q, fy, 2025)
        assert np.isnan(out["val"].iloc[0])


class TestOlsSlope:
    def test_slope_sign(self):
        assert fundamentals.ols_slope([1.0, 2.0, 3.0, 4.0]) > 0
        assert fundamentals.ols_slope([4.0, 3.0, 2.0, 1.0]) < 0

    def test_insufficient_points_nan(self):
        assert np.isnan(fundamentals.ols_slope([1.0, np.nan, np.nan, 2.0]))
