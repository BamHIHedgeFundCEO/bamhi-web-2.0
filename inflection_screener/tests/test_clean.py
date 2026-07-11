"""清洗層單元測試：Q4 推導、coalesce、去重（spec §7 / 驗收 #1）。"""
import numpy as np
import pandas as pd

from inflection_screener.src import clean

C606 = "RevenueFromContractWithCustomerExcludingAssessedTax"


def _fact(cik, concept, end, val, accn="0001-24-000001", frame="CY2025Q1", filed=None, year=2025, q=1):
    row = {"cik": cik, "entity": f"Co{cik}", "start": None, "end": end,
           "val": val, "accn": accn, "concept": concept, "frame": frame,
           "year": year, "q": q}
    if filed is not None:
        row["filed"] = filed
    return row


class TestCoalesce:
    def test_priority_606_first(self):
        facts = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 900),
            _fact(1, C606, "2025-03-31", 1000),
            _fact(1, "SalesRevenueNet", "2025-03-31", 800),
        ])
        out = clean.coalesce_revenue(facts)
        assert len(out) == 1
        assert out["val"].iloc[0] == 1000  # 606 tag 優先

    def test_fallback_when_606_missing(self):
        facts = pd.DataFrame([
            _fact(2, "Revenues", "2025-03-31", 900),
            _fact(2, "SalesRevenueNet", "2025-03-31", 800),
        ])
        out = clean.coalesce_revenue(facts)
        assert out["val"].iloc[0] == 900


class TestDedupe:
    def test_keep_latest_filed(self):
        facts = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 500, accn="a", filed="2025-05-01"),
            _fact(1, "Revenues", "2025-03-31", 555, accn="b", filed="2025-08-01"),  # 修正後重申報
        ])
        out = clean.dedupe_facts(facts)
        assert len(out) == 1
        assert out["val"].iloc[0] == 555

    def test_fallback_accn_order(self):
        facts = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 500, accn="0001-25-000001"),
            _fact(1, "Revenues", "2025-03-31", 555, accn="0001-25-000099"),
        ])
        out = clean.dedupe_facts(facts)
        assert out["val"].iloc[0] == 555


class TestQ4Derivation:
    def _fy(self, cik, val):
        return _fact(cik, "Revenues", "2025-12-31", val, frame="CY2025", year=2025, q=0)

    def test_q4_equals_fy_minus_three_quarters(self):
        q = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 20, frame="CY2025Q1", q=1),
            _fact(1, "Revenues", "2025-06-30", 30, frame="CY2025Q2", q=2),
            _fact(1, "Revenues", "2025-09-30", 25, frame="CY2025Q3", q=3),
        ])[["cik", "year", "q", "end", "val", "accn"]]
        fy = pd.DataFrame([self._fy(1, 100)])[["cik", "year", "q", "end", "val", "accn"]]
        out = clean.derive_q4(q, fy, 2025)
        assert len(out) == 1
        assert out["val"].iloc[0] == 25  # 100 − (20+30+25)

    def test_missing_q2_returns_nan(self):
        """驗收 #1(c)：缺 Q2 時 Q4 必須回傳 NaN，不得硬補。"""
        q = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 20, frame="CY2025Q1", q=1),
            _fact(1, "Revenues", "2025-09-30", 25, frame="CY2025Q3", q=3),
        ])[["cik", "year", "q", "end", "val", "accn"]]
        fy = pd.DataFrame([self._fy(1, 100)])[["cik", "year", "q", "end", "val", "accn"]]
        out = clean.derive_q4(q, fy, 2025)
        assert len(out) == 1
        assert np.isnan(out["val"].iloc[0])

    def test_existing_q4_not_overwritten(self):
        q = pd.DataFrame([
            _fact(1, "Revenues", "2025-03-31", 20, frame="CY2025Q1", q=1),
            _fact(1, "Revenues", "2025-06-30", 30, frame="CY2025Q2", q=2),
            _fact(1, "Revenues", "2025-09-30", 25, frame="CY2025Q3", q=3),
            _fact(1, "Revenues", "2025-12-31", 99, frame="CY2025Q4", q=4),
        ])[["cik", "year", "q", "end", "val", "accn"]]
        fy = pd.DataFrame([self._fy(1, 100)])[["cik", "year", "q", "end", "val", "accn"]]
        out = clean.derive_q4(q, fy, 2025)
        assert out.empty  # 已有 Q4，不追加
