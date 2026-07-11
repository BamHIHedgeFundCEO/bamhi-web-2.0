"""指標層：營收 YoY + Accel（二階）/ 淨利率斜率 / 由負轉正偵測（spec §4）。

⚠ 淨利 / EPS 禁用 YoY% 成長率（負值變號會使符號錯亂），
一律用 level / margin 的 OLS 斜率（spec §4.2）。
"""
import numpy as np
import pandas as pd

from inflection_screener import config


def ols_slope(values) -> float:
    """OLS 斜率，x = 0..n-1，忽略 NaN；有效點 < 3 → NaN。"""
    y = np.asarray(values, dtype=float)
    x = np.arange(len(y), dtype=float)
    mask = np.isfinite(y)
    if mask.sum() < 3:
        return np.nan
    return float(np.polyfit(x[mask], y[mask], 1)[0])


def _company_metrics(g: pd.DataFrame) -> dict | None:
    """單一公司逐季序列 → 最新季指標。g 需按 (year, q) 排序。"""
    r = g["revenue"].astype(float).reset_index(drop=True)
    ni = g["net_income"].astype(float).reset_index(drop=True)
    eps = g["eps_diluted"].astype(float).reset_index(drop=True)

    # 最新季 = 該公司已出現數據的最近 period_end（spec §4.1，各自最新為準）
    valid = r.notna()
    if not valid.any():
        return None
    t = int(valid[valid].index[-1])
    if t < 6:  # 連兩季 Accel 至少需 7 季（spec §4.1）
        return None

    # YoY_t = R_t / R_{t-4} − 1，需 R_{t-4} > 0
    r4 = r.shift(4)
    yoy = pd.Series(np.where(r4 > 0, r / r4 - 1, np.nan), index=r.index)
    accel = yoy.diff()

    yoy_t = yoy.iloc[t]
    accel_t = accel.iloc[t]
    accel_t1 = accel.iloc[t - 1]

    # 淨利率斜率（近 4 季）；R <= 0 的季 margin 記 NaN
    margin = pd.Series(np.where(r > 0, ni / r, np.nan), index=r.index)
    margin_slope = ols_slope(margin.iloc[max(0, t - 3): t + 1])
    eps_slope = ols_slope(eps.iloc[max(0, t - 3): t + 1])

    # 由負轉正偵測（spec §4.3）
    ni_t, ni_t1 = ni.iloc[t], ni.iloc[t - 1]
    flag_turn_positive = bool(
        pd.notna(ni_t) and pd.notna(ni_t1) and ni_t1 < 0 and ni_t >= 0
    )
    margin_t = margin.iloc[t]
    flag_near_positive = bool(
        pd.notna(ni_t) and ni_t < 0
        and pd.notna(margin_slope) and margin_slope > 0
        and pd.notna(margin_t) and (margin_t + margin_slope) >= 0
    )

    return {
        "cik": g["cik"].iloc[0],
        "latest_period": g["period_end"].iloc[t],
        "accn": g["accn"].iloc[t],
        "filing_date": g["filing_date"].iloc[t],
        "data_quality": g["data_quality"].iloc[0],
        "yoy_t": float(yoy_t) if pd.notna(yoy_t) else np.nan,
        "accel_t": float(accel_t) if pd.notna(accel_t) else np.nan,
        "accel_t1": float(accel_t1) if pd.notna(accel_t1) else np.nan,
        "margin_slope": margin_slope,
        "eps_slope": eps_slope,
        "flag_turn_positive": flag_turn_positive,
        "flag_near_positive": flag_near_positive,
    }


def compute_metrics(qtable: pd.DataFrame) -> pd.DataFrame:
    """逐季寬表 → 每公司一列的最新季指標表。

    data_quality='partial' 排除於加速度計算（spec §3.4）。
    """
    if qtable.empty:
        return pd.DataFrame()
    ok = qtable[qtable["data_quality"] == "ok"]
    rows = []
    for _, g in ok.sort_values(["cik", "year", "q"]).groupby("cik", sort=False):
        m = _company_metrics(g)
        if m is not None:
            rows.append(m)
    df = pd.DataFrame(rows)
    print(f"[fundamentals] 可計算指標公司數={len(df)}", flush=True)
    return df


def passes_accel_gate(row) -> bool:
    """閘門 ②：營收加速（spec §5.2，唯一淘汰性基本面條件）。

    YoY_t >= YOY_MIN 且 Accel_t > 0 且 Accel_{t-1} > 0（連兩季，濾一次性基期效應）。
    """
    return bool(
        pd.notna(row["yoy_t"]) and row["yoy_t"] >= config.YOY_MIN
        and pd.notna(row["accel_t"]) and row["accel_t"] > 0
        and pd.notna(row["accel_t1"]) and row["accel_t1"] > 0
    )
