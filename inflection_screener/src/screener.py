"""篩選層：閘門邏輯 + 排序 + 兩池組裝（spec §5）。

流程：閘門②營收加速（先，省 yfinance 呼叫）→ 閘門①流動性 → 左側池
→ 技術模板 + RS → 右側池。
"""
import numpy as np
import pandas as pd

from inflection_screener import config
from inflection_screener.src import fundamentals, prices, technicals


def accel_candidates(metrics: pd.DataFrame) -> pd.DataFrame:
    """閘門 ②：營收加速通過者（唯一淘汰性基本面條件）。"""
    if metrics.empty:
        return metrics
    mask = metrics.apply(fundamentals.passes_accel_gate, axis=1)
    out = metrics[mask].reset_index(drop=True)
    print(f"[screener] 閘門② 營收加速：{len(metrics)} → {len(out)}", flush=True)
    return out


def _flags_str(row) -> str:
    parts = []
    if row.get("flag_turn_positive"):
        parts.append("🔺翻正")
    if row.get("flag_near_positive"):
        parts.append("🔺近轉正")
    if row.get("rs_line_high"):
        parts.append("🔺RS領先")
    return "|".join(parts)


def assemble_left(
    candidates: pd.DataFrame,
    hists: dict[str, pd.DataFrame],
    caps: dict[str, float],
) -> pd.DataFrame:
    """閘門 ① + 排序分數 → 左側池。candidates 需已 merge ticker/name。"""
    rows = []
    for _, r in candidates.iterrows():
        t = r["ticker"]
        if t not in hists:
            continue
        snap = prices.snapshot(hists[t])
        mc = caps.get(t, np.nan)
        if not prices.passes_liquidity_gate(mc, snap["price"], snap["dollar_vol_20d"]):
            continue
        rows.append({**r.to_dict(), "market_cap": mc, **snap})

    left = pd.DataFrame(rows)
    if left.empty:
        print("[screener] 左側池：0 檔", flush=True)
        return left

    # score = rank(margin_slope)×0.5 + rank(eps_slope)×0.3 + rank(Accel_t)×0.2（spec §5.3）
    def _rank(col):
        return left[col].rank(pct=True).fillna(0.0)

    left["score"] = (
        _rank("margin_slope") * config.SCORE_W_MARGIN_SLOPE
        + _rank("eps_slope") * config.SCORE_W_EPS_SLOPE
        + _rank("accel_t") * config.SCORE_W_ACCEL
    )
    # 🔺旗標無條件置頂（旗標優先於分數）
    left["_flagged"] = left["flag_turn_positive"] | left["flag_near_positive"]
    left["flags"] = left.apply(_flags_str, axis=1)
    left = left.sort_values(["_flagged", "score"], ascending=[False, False]).drop(
        columns="_flagged"
    ).reset_index(drop=True)
    print(f"[screener] 左側池：{len(left)} 檔", flush=True)
    return left


def assemble_right(left: pd.DataFrame, hists: dict[str, pd.DataFrame], spy_close: pd.Series) -> pd.DataFrame:
    """右側池 = 左側池 ∩ 週線全過 ∩ 日線 D1–D5 全過 ∩ RS_rank ≥ 80。"""
    if left.empty:
        return pd.DataFrame()

    tech = {}
    for t in left["ticker"]:
        if t in hists:
            tech[t] = technicals.evaluate(hists[t], spy_close)

    tdf = pd.DataFrame.from_dict(tech, orient="index")
    tdf.index.name = "ticker"
    tdf = tdf.reset_index()

    # RS_rank：橫截面百分位，母體 = 全部左側池成員（spec §5.4）
    tdf["rs_rank"] = tdf["rs_raw"].rank(pct=True) * 100

    merged = left.merge(tdf, on="ticker", how="left")
    passed = merged[
        merged["weekly_pass"].fillna(False)
        & merged["trend_template_pass"].fillna(False)
        & (merged["rs_rank"] >= config.RS_RANK_MIN)
    ].copy()

    if passed.empty:
        print("[screener] 右側池：0 檔", flush=True)
        return passed

    passed["flags"] = passed.apply(_flags_str, axis=1)
    passed["_top"] = (
        passed["rs_line_high"] | passed["flag_turn_positive"] | passed["flag_near_positive"]
    )
    passed = passed.sort_values(["_top", "rs_rank"], ascending=[False, False]).drop(
        columns="_top"
    ).reset_index(drop=True)
    print(f"[screener] 右側池：{len(passed)} 檔", flush=True)
    return passed
