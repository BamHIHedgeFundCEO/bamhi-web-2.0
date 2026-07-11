"""清洗層：營收 tag coalesce / Q4 單季推導 / 去重 point-in-time（spec §3）。"""
import re

import numpy as np
import pandas as pd

from inflection_screener import config

_FRAME_Q_RE = re.compile(r"^CY(\d{4})Q([1-4])$")
_FRAME_Y_RE = re.compile(r"^CY(\d{4})$")


def dedupe_facts(df: pd.DataFrame) -> pd.DataFrame:
    """同一 (cik, concept, period_end) 取申報最新一筆（spec §3.3 ⚠）。

    Frames API 已由 SEC 伺服端每季每公司選一筆、且不含 filed 欄位；
    此函式為通用實作：有 `filed` 欄位時以 filed 最新優先，否則以 accn
    字典序最大（accession 編號隨時間遞增）作為次序鍵。
    """
    if df.empty:
        return df
    sort_cols = []
    if "filed" in df.columns:
        df = df.copy()
        df["filed"] = pd.to_datetime(df["filed"], errors="coerce")
        sort_cols.append("filed")
    if "accn" in df.columns:
        sort_cols.append("accn")
    if sort_cols:
        df = df.sort_values(sort_cols, na_position="first")
    return df.drop_duplicates(subset=["cik", "concept", "end"], keep="last")


def _parse_frame_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """從 frame 字串解析 (year, q)；年度 frame q=0。"""
    df = df.copy()
    years, qs = [], []
    for f in df["frame"]:
        m = _FRAME_Q_RE.match(f)
        if m:
            years.append(int(m.group(1)))
            qs.append(int(m.group(2)))
            continue
        m = _FRAME_Y_RE.match(f)
        if m:
            years.append(int(m.group(1)))
            qs.append(0)
        else:
            years.append(np.nan)
            qs.append(np.nan)
    df["year"], df["q"] = years, qs
    return df


def coalesce_revenue(facts: pd.DataFrame) -> pd.DataFrame:
    """營收 tag coalesce（spec §3.1）：按優先序取第一個非空。

    三 tag 皆有且值不同 → 取 606 tag 並 log 警告。
    輸入需含 year/q 欄位；輸出 (cik, year, q, end, val, accn)。
    """
    rev = facts[facts["concept"].isin(config.REVENUE_CONCEPTS)]
    if rev.empty:
        return pd.DataFrame(columns=["cik", "year", "q", "end", "val", "accn"])

    prio = {c: i for i, c in enumerate(config.REVENUE_CONCEPTS)}
    rev = rev.copy()
    rev["_prio"] = rev["concept"].map(prio)
    rev = rev.sort_values("_prio")

    # 衝突偵測：同 (cik, year, q) 多 tag 且值不同
    grp = rev.groupby(["cik", "year", "q"])["val"]
    n_conflict = int((grp.nunique() > 1).sum())
    if n_conflict:
        print(f"[clean] 營收 tag 衝突 {n_conflict} 筆（多 tag 值不同），取 606 優先 tag", flush=True)

    out = rev.drop_duplicates(subset=["cik", "year", "q"], keep="first")
    return out[["cik", "year", "q", "end", "val", "accn"]]


def _single_concept(facts: pd.DataFrame, concept: str) -> pd.DataFrame:
    df = facts[facts["concept"] == concept]
    if df.empty:
        return pd.DataFrame(columns=["cik", "year", "q", "end", "val", "accn"])
    return df.drop_duplicates(subset=["cik", "year", "q"], keep="last")[
        ["cik", "year", "q", "end", "val", "accn"]
    ]


def derive_q4(metric_q: pd.DataFrame, metric_fy: pd.DataFrame, year: int) -> pd.DataFrame:
    """Q4 單季 = FY − (Q1+Q2+Q3)（spec §3.2 ⚠）。

    前三季任一缺失 → 該公司該年 Q4 = NaN，不得硬補。
    只補「該年 Q4 frame 沒出現」的公司；已有 Q4 者不動。
    回傳需追加的 Q4 rows（val 可為 NaN）。
    """
    fy = metric_fy[metric_fy["year"] == year]
    if fy.empty:
        return pd.DataFrame(columns=["cik", "year", "q", "end", "val", "accn"])

    qs = metric_q[metric_q["year"] == year]
    have_q4 = set(qs.loc[qs["q"] == 4, "cik"])
    q123 = qs[qs["q"].isin([1, 2, 3])].pivot_table(
        index="cik", columns="q", values="val", aggfunc="last"
    )

    rows = []
    for _, r in fy.iterrows():
        cik = r["cik"]
        if cik in have_q4:
            continue
        val = np.nan
        if cik in q123.index:
            trio = q123.loc[cik].reindex([1, 2, 3])
            if trio.notna().all():
                val = float(r["val"]) - float(trio.sum())
        rows.append({"cik": cik, "year": year, "q": 4, "end": r["end"], "val": val, "accn": r["accn"]})
    return pd.DataFrame(rows)


def build_quarterly_table(
    quarterly: pd.DataFrame, annual: pd.DataFrame, window: list[tuple[int, int]]
) -> pd.DataFrame:
    """組裝逐季寬表：cik, year, q, period_end, revenue, net_income, eps_diluted,
    accn, filing_date(NULL v1), data_quality。僅保留窗口內的季。"""
    if quarterly.empty:
        return pd.DataFrame()

    quarterly = _parse_frame_quarter(dedupe_facts(quarterly))
    annual = _parse_frame_quarter(dedupe_facts(annual)) if not annual.empty else pd.DataFrame(
        columns=["cik", "concept", "year", "q", "end", "val", "accn"]
    )

    rev_q = coalesce_revenue(quarterly)
    ni_q = _single_concept(quarterly, config.NET_INCOME_CONCEPT)
    eps_q = _single_concept(quarterly, config.EPS_CONCEPT)
    rev_fy = coalesce_revenue(annual)
    ni_fy = _single_concept(annual, config.NET_INCOME_CONCEPT)

    # Q4 推導：Revenues 與 NetIncomeLoss；EPS 不做（非可加性，spec §3.2）
    q4_years = sorted({y for (y, q) in window if q == 4})
    for y in q4_years:
        rev_q = pd.concat([rev_q, derive_q4(rev_q, rev_fy, y)], ignore_index=True)
        ni_q = pd.concat([ni_q, derive_q4(ni_q, ni_fy, y)], ignore_index=True)

    def _slim(df: pd.DataFrame, name: str) -> pd.DataFrame:
        return df.rename(columns={"val": name}).set_index(["cik", "year", "q"])[[name, "end"]]

    r, n, e = _slim(rev_q, "revenue"), _slim(ni_q, "net_income"), _slim(eps_q, "eps_diluted")
    wide = r[["revenue"]].join(n[["net_income"]], how="outer").join(e[["eps_diluted"]], how="outer")

    # period_end：優先取營收 fact 的 end，缺則 NI、再 EPS
    end = r["end"].rename("e1").to_frame().join(n["end"].rename("e2"), how="outer").join(
        e["end"].rename("e3"), how="outer"
    )
    wide["period_end"] = end["e1"].fillna(end["e2"]).fillna(end["e3"])
    wide["accn"] = rev_q.set_index(["cik", "year", "q"])["accn"].reindex(wide.index)
    wide = wide.reset_index()

    # 只留窗口內的季
    win = set(window)
    wide = wide[[(y, q) in win for y, q in zip(wide["year"], wide["q"])]].copy()

    # data_quality（spec §3.4）：窗口 8 季內缺 ≥ 2 季營收 → partial
    n_have = wide[wide["revenue"].notna()].groupby("cik")["q"].size()
    missing = len(window) - n_have.reindex(wide["cik"].unique()).fillna(0)
    quality = (missing >= config.PARTIAL_MISSING_THRESHOLD).map({True: "partial", False: "ok"})
    wide["data_quality"] = wide["cik"].map(quality)
    wide["filing_date"] = None  # Frames 無 filed 欄位；v1 留空，accn 供未來反查

    n_partial = int((quality == "partial").sum())
    print(f"[clean] 公司數={quality.size}, partial={n_partial}（排除於加速度計算）", flush=True)
    return wide.sort_values(["cik", "year", "q"]).reset_index(drop=True)
