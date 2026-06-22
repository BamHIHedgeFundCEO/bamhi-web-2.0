"""板塊輪動與 VCP 掃描引擎 (移植自 data_engine/market/sector_engine.py
+ views/_sector_charts.py 的 RRG/相關係數邏輯)。

純 pandas / numpy；yfinance 僅用於全板塊唯一一次 bulk download，
依 period 行程內快取，overview 與 detail 共用。
"""
import gc
import hashlib
import json
import os
import time

import numpy as np
import pandas as pd

from backend.config.sectors import SECTOR_LEADERS, TRACKED_SECTORS

# bulk download 快取：period → {ts, data}，最多保留 2 個 period
_BULK_CACHE: dict = {}
_BULK_TTL = 3600
_BULK_MAX = 2

RRG_SHORT = 14
RRG_LONG = 50

# 預先算好的 JSON 目錄 (由 pipeline 產出，後端優先讀檔以求秒開)
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRECOMPUTE_DIR = os.path.join(_BASE_DIR, "data", "sector_rotation")
PRECOMPUTE_PERIOD = "2y"  # 預算好的區間；其他區間才即時計算


def _detail_filename(sector: str) -> str:
    return f"detail_{hashlib.md5(sector.encode('utf-8')).hexdigest()[:12]}.json"


def _load_precomputed(filename: str):
    path = os.path.join(PRECOMPUTE_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[sector_rotation] 讀預算檔失敗 {filename}: {e}")
        return None


# ── 對外：優先讀預算檔，沒有才即時計算 (router 呼叫這三個) ──
def overview_cached(period: str):
    if period == PRECOMPUTE_PERIOD:
        data = _load_precomputed("overview.json")
        if data is not None:
            return data
    return get_overview(period)


def signals_cached(period: str):
    # 訊號是「當下狀態快照」，不分區間都用最新預算檔，避免線上即時下載
    data = _load_precomputed("signals.json")
    if data is not None:
        return data
    return get_signals(period)


def detail_cached(sector: str, period: str):
    if sector not in TRACKED_SECTORS:
        return None
    if period == PRECOMPUTE_PERIOD:
        data = _load_precomputed(_detail_filename(sector))
        if data is not None:
            return data
    return get_detail(sector, period)


def _all_unique_tickers() -> list[str]:
    s = {"SPY"}
    for tickers in TRACKED_SECTORS.values():
        s.update(tickers)
    return sorted(s)


def _get_bulk(period: str) -> pd.DataFrame:
    cached = _BULK_CACHE.get(period)
    if cached and time.time() - cached["ts"] < _BULK_TTL:
        return cached["data"]
    import yfinance as yf

    raw = yf.download(_all_unique_tickers(), period=period, progress=False, auto_adjust=False)
    # downcast float64 → float32 to halve RAM for this large MultiIndex DataFrame
    for col in raw.select_dtypes("float64").columns:
        raw[col] = raw[col].astype("float32")
    if len(_BULK_CACHE) >= _BULK_MAX:
        oldest = min(_BULK_CACHE, key=lambda k: _BULK_CACHE[k]["ts"])
        del _BULK_CACHE[oldest]
    _BULK_CACHE[period] = {"ts": time.time(), "data": raw}
    gc.collect()
    return raw


# ── 板塊綜合指標 (移植 calculate_sector_metrics) ──
def compute_sector_metrics(tickers: list[str], raw_data: pd.DataFrame) -> pd.DataFrame | None:
    if not tickers or raw_data is None or raw_data.empty:
        return None

    data = raw_data["Close"]
    vol_data = raw_data["Volume"]
    open_data, high_data, low_data = raw_data["Open"], raw_data["High"], raw_data["Low"]
    if data.empty or vol_data.empty or "SPY" not in data.columns:
        return None

    valid = [t for t in tickers if t in data.columns]
    if not valid:
        return None

    prev_close = data[valid].shift(1)
    ret_close = ((data[valid] - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_open = ((open_data[valid] - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_high = ((high_data[valid] - prev_close) / prev_close).clip(-0.95, 2.0)
    ret_low = ((low_data[valid] - prev_close) / prev_close).clip(-0.95, 2.0)

    valid_mask = data[valid].notna().sum(axis=1) > 0
    sector_index = ((1 + ret_close.mean(axis=1).fillna(0)).cumprod() * 100).where(valid_mask, np.nan)
    prev_si = sector_index.shift(1).fillna(100).where(valid_mask, np.nan)
    sector_open = prev_si * (1 + ret_open.mean(axis=1).fillna(0))
    sector_high = prev_si * (1 + ret_high.mean(axis=1).fillna(0))
    sector_low = prev_si * (1 + ret_low.mean(axis=1).fillna(0))

    spy_price = data["SPY"]
    rs_raw = sector_index / spy_price
    rs_line = rs_raw / rs_raw.dropna().iloc[0] if not rs_raw.dropna().empty else rs_raw
    rs_slope = rs_line.diff(5)

    if not spy_price[valid_mask].dropna().empty:
        spy_norm = (spy_price / spy_price[valid_mask].dropna().iloc[0] * 100).where(valid_mask, np.nan)
    else:
        spy_norm = spy_price / spy_price.iloc[0] * 100

    rs_ratio = (rs_line.rolling(RRG_SHORT).mean() / rs_line.rolling(RRG_LONG).mean()) * 100
    rs_momentum = (rs_ratio / rs_ratio.rolling(RRG_SHORT).mean()) * 100

    stocks_ma20 = data[valid].rolling(20).mean()
    breadth = (((data[valid] > stocks_ma20).sum(axis=1)) / data[valid].notna().sum(axis=1).replace(0, np.nan) * 100).where(valid_mask, np.nan)

    dollar_vol = data * vol_data
    sec_dv = dollar_vol[valid].sum(axis=1)
    spy_dv_smooth = dollar_vol["SPY"].rolling(20).mean()
    crowd = sec_dv / (spy_dv_smooth + 1e-9)
    crowd_90p = crowd.rolling(250).quantile(0.9)

    daily_ret = sector_index.pct_change()
    up_dv = (sec_dv * (daily_ret > 0).astype(float)).rolling(20).sum()
    down_dv = (sec_dv * (daily_ret < 0).astype(float)).rolling(20).sum()
    ud_dv = up_dv / down_dv.replace(0, np.nan)

    df = pd.DataFrame({
        "Sector_Open": sector_open, "Sector_High": sector_high, "Sector_Low": sector_low,
        "Sector_Close": sector_index, "MA10": sector_index.rolling(10).mean(),
        "MA20": sector_index.rolling(20).mean(), "MA60": sector_index.rolling(60).mean(),
        "MA120": sector_index.rolling(120).mean(), "MA200": sector_index.rolling(200).mean(),
        "SPY_Index": spy_norm, "M5": sector_index.pct_change(5) * 100,
        "M10": sector_index.pct_change(10) * 100, "M20": sector_index.pct_change(20) * 100,
        "RS_Line": rs_line, "RS_Slope": rs_slope, "RS_Ratio": rs_ratio, "RS_Momentum": rs_momentum,
        "Sector_Breadth": breadth, "Crowdedness": crowd, "Crowdedness_90p": crowd_90p, "UD_DV_Ratio": ud_dv,
    })
    df["Momentum_Diff"] = df["M10"] - df["M20"]
    fvi = sector_index.first_valid_index()
    return df.loc[fvi:] if fvi is not None else df


# ── VCP 評分權重 (可調) ───────────────────────────────────────────
# 設計原則：trend_pass 是「閘門」不是分數——沒過上升趨勢模板的票，分數會被
# 折到 GATE_FAIL_FACTOR(壓到榜尾)，因為 VCP 的前提就是已在確認的上升趨勢。
# 其餘 6 項加總 = 100，重心放在「相對強弱 + VCP 結構(收斂/收緊) + 吸籌」。
VCP_WEIGHTS = {
    "rs": 25,         # 相對強弱(板塊內 RS 百分位)——實證最強的領先指標
    "converge": 20,   # 連續波動收斂(真 VCP 結構)
    "tight": 10,      # 最新一段收得多緊
    "accum": 20,      # 吸籌(漲量 ÷ 跌量)
    "dry": 10,        # 量能枯竭(突破前沉默)
    "near_high": 15,  # 貼近 52 週高(8% 內線性給分；不與趨勢閘門重複計)
}
GATE_FAIL_FACTOR = 0.2  # 未過 trend_pass 的折扣(保留排序資訊但壓到榜尾)


# ── VCP 掃描 (移植 scan_vcp_candidates) ──
def scan_vcp(tickers: list[str], raw_data: pd.DataFrame) -> list[dict]:
    if raw_data is None or raw_data.empty:
        return []
    close_data, vol_data = raw_data["Close"], raw_data["Volume"]
    high_data, low_data = raw_data["High"], raw_data["Low"]

    valid = [t for t in tickers if t in close_data.columns and t != "SPY"]
    if not valid:
        return []
    df_c, df_v, df_h, df_l = close_data[valid], vol_data[valid], high_data[valid], low_data[valid]
    mask = df_c.notna().sum() >= 200
    valid = mask[mask].index.tolist()
    if not valid:
        return []
    df_c, df_v, df_h, df_l = df_c[valid], df_v[valid], df_h[valid], df_l[valid]

    spy_3m = 0.0
    if "SPY" in close_data.columns:
        spy_close = close_data["SPY"].dropna()
        if len(spy_close) >= 60:
            spy_3m = spy_close.pct_change(60).iloc[-1] * 100

    # ffill so last row is last valid trading day (today may be NaN if market not closed)
    df_c_f = df_c.ffill()
    df_v_f = df_v.ffill()
    df_h_f = df_h.ffill()
    df_l_f = df_l.ffill()
    close_last, vol_last = df_c_f.iloc[-1], df_v_f.iloc[-1]
    ma50, ma150, ma200 = df_c_f.rolling(50).mean().iloc[-1], df_c_f.rolling(150).mean().iloc[-1], df_c_f.rolling(200).mean().iloc[-1]
    high_52w = df_c_f.iloc[-252:].max()
    trend_pass = (close_last > ma150) & (close_last > ma200) & (ma50 > ma150) & (close_last >= high_52w * 0.75)

    tr = df_h_f - df_l_f
    safe_close = close_last.replace(0, 1)
    atr_now = tr.iloc[-5:].mean() / safe_close * 100
    atr_base = tr.iloc[-20:].mean() / safe_close * 100
    atr_contr = pd.Series(np.where(atr_base > 0, atr_now / atr_base, 1.0), index=valid)

    # 多段波動收縮 (真 VCP：連續、且一次比一次小的回檔)。
    # 近 60 交易日切 3 段(各 20 日)，比較每段「高低區間 ÷ 均價」，逐段變小 = 波動收斂，
    # 比單一 5d/20d 比值更貼近 VCP 的「連續收縮」結構。
    def _win_range(sl):
        base = df_c_f.iloc[sl].mean().replace(0, np.nan)
        return (df_h_f.iloc[sl].max() - df_l_f.iloc[sl].min()) / base * 100

    r_old, r_mid, r_new = _win_range(slice(-60, -40)), _win_range(slice(-40, -20)), _win_range(slice(-20, None))
    shrink1, shrink2 = r_mid < r_old, r_new < r_mid
    contractions = shrink1.astype(int) + shrink2.astype(int)          # 0~2 段收縮
    converging = shrink1 & shrink2                                    # 連續收斂
    tightness = (1 - r_new / r_old.replace(0, np.nan)).clip(0, 1).fillna(0)  # 收得多緊 0~1
    contraction_ok = converging & (r_new < 12)                        # 連續收斂 + 最新段夠緊

    vol_ma20 = df_v_f.rolling(20).mean().iloc[-1]
    vol_dry = vol_last < vol_ma20 * 0.6
    ret_50 = df_c_f.iloc[-50:].pct_change()
    up_vol = (df_v_f.iloc[-50:] * (ret_50 > 0)).sum()
    down_vol = (df_v_f.iloc[-50:] * (ret_50 < 0)).sum()
    ud_ratio = pd.Series(np.where(down_vol > 0, up_vol / down_vol, 0.0), index=valid)

    ma20 = df_c_f.rolling(20).mean().iloc[-1]
    dist_ma20 = np.where(ma20 > 0, (close_last / ma20 - 1) * 100, 0)
    m1, m10 = df_c_f.pct_change(1).iloc[-1] * 100, df_c_f.pct_change(10).iloc[-1] * 100
    m20, m60 = df_c_f.pct_change(20).iloc[-1] * 100, df_c_f.pct_change(60).iloc[-1] * 100
    rs_3m = df_c_f.pct_change(60).iloc[-1] * 100 - spy_3m
    dist_high = (close_last / high_52w - 1) * 100

    res = pd.DataFrame({
        "ticker": valid, "price": close_last.round(2).values,
        "m1": m1.round(2).values, "m10": m10.round(2).values, "m20": m20.round(2).values, "m60": m60.round(2).values,
        "dist_ma20": pd.Series(dist_ma20).round(2).values, "atr_pct": atr_now.round(2).values,
        "atr_contraction": atr_contr.round(2).values, "up_down_vol": ud_ratio.round(2).values,
        "rs_3m": rs_3m.round(2).values, "dist_to_high": dist_high.round(1).values,
        "trend_pass": trend_pass.values, "vol_dry_up": vol_dry.values,
        "contractions": contractions.values, "contraction_ok": contraction_ok.values,
    })
    # rs_3m 可能含 NaN（新股/資料不足）→ rank 出 NaN，需先補 0 再轉 int，否則 astype 會炸
    res["rs_rank"] = res["rs_3m"].rank(pct=True).mul(100).round(0).fillna(0).astype(int)

    # 綜合 VCP 評分：其餘 6 項加總 0~100，再乘趨勢閘門折扣
    w = VCP_WEIGHTS
    near_high = np.nan_to_num(np.clip(1 + dist_high.values / 8.0, 0, 1))  # 離 52 週高 8% 內線性給分
    quality = (
        w["rs"] * (res["rs_rank"].values / 100.0)
        + w["converge"] * converging.values.astype(float)
        + w["tight"] * tightness.values
        + w["accum"] * np.clip(ud_ratio.values / 2.0, 0, 1)
        + w["dry"] * vol_dry.values.astype(float)
        + w["near_high"] * near_high
    )
    # 趨勢閘門：沒過上升趨勢模板 → 折到 GATE_FAIL_FACTOR(壓到榜尾)
    gate = np.where(trend_pass.values, 1.0, GATE_FAIL_FACTOR)
    res["vcp_score"] = np.round(np.nan_to_num(quality * gate), 0).astype(int)
    # 🎯 高把握組合：趨勢過 + 連續收斂 + 吸籌(漲量>跌量) + 跑贏大盤
    res["vcp_pass"] = (trend_pass.values & converging.values & (ud_ratio.values > 1) & (rs_3m.values > 0))
    res = res.sort_values("vcp_score", ascending=False).reset_index(drop=True)

    records = res.where(pd.notnull(res), None).to_dict(orient="records")
    # 加上 60 日走勢迷你線 (取自已下載的收盤序列)
    for r in records:
        s = df_c[r["ticker"]].dropna().tail(60)
        r["trend"] = [round(float(x), 2) for x in s.tolist()]
    return records


def rrg_quadrant(rs_ratio: float, rs_momentum: float) -> dict:
    if rs_ratio > 100 and rs_momentum > 100:
        return {"label": "🟢 領先 Leading", "color": "#22c55e", "desc": "強勢加速，主升段核心板塊"}
    if rs_ratio > 100:
        return {"label": "🟡 轉弱 Weakening", "color": "#eab308", "desc": "強勢但動能減速，注意高點風險"}
    if rs_ratio <= 100 and rs_momentum <= 100:
        return {"label": "🔴 落後 Lagging", "color": "#ef4444", "desc": "弱勢且加速惡化，建議觀望"}
    return {"label": "🔵 改善 Improving", "color": "#3b82f6", "desc": "弱勢但動能回升，潛在輪動候選"}


def _signal_from_df(df: pd.DataFrame) -> dict:
    """從板塊 df 推導首頁訊號 (對應 components/sector_signals.get_signal_for_sector)。"""
    last = df.iloc[-1]
    close_v = float(last.get("Sector_Close", 0))
    ma20_v = float(last.get("MA20", 0)) if pd.notna(last.get("MA20")) else 0
    ma60_v = float(last.get("MA60", 0)) if pd.notna(last.get("MA60")) else 0
    rs_slope = float(last.get("RS_Slope", 0)) if pd.notna(last.get("RS_Slope")) else 0
    m10 = float(last.get("M10", 0)) if pd.notna(last.get("M10")) else 0
    crowd = float(last.get("Crowdedness", 0)) * 100 if pd.notna(last.get("Crowdedness")) else 0
    crowd90 = float(last.get("Crowdedness_90p", 0)) * 100 if pd.notna(last.get("Crowdedness_90p")) else 999

    if crowd >= crowd90 and crowd90 > 0:
        return {"emoji": "🚨", "status": "過熱警報", "color": "red",
                "detail": f"擁擠度 {crowd:.1f}% 突破 90 分位 {crowd90:.1f}%，籌碼極度擁擠，注意大戶派發風險！"}
    if close_v < ma20_v:
        return {"emoji": "🔴", "status": "空頭弱勢", "color": "orange",
                "detail": f"指數跌破月線（收盤 {close_v:.2f} < MA20 {ma20_v:.2f}），建議觀望。"}
    if close_v > ma20_v and ma20_v > ma60_v and rs_slope > 0 and m10 > 0:
        return {"emoji": "🟢", "status": "強勢多頭", "color": "green",
                "detail": "Close > MA20 > MA60，RS 向上發散，主升段，可尋找 VCP 突破點。"}
    if close_v > ma20_v and rs_slope > 0:
        return {"emoji": "🔵", "status": "初步轉強", "color": "blue",
                "detail": "指數剛站上月線且 RS 翻轉向上，有落底回升跡象，可關注 VCP 候選股。"}
    return {"emoji": "🟡", "status": "整理蓄力", "color": "yellow",
            "detail": "月線之上但動能衰減或 RS 下滑，板塊可能橫盤消化或面臨賣壓。"}


def get_signals(period: str = "1y"):
    raw = _get_bulk(period)
    if raw is None or raw.empty:
        return None
    out = []
    for name, tickers in TRACKED_SECTORS.items():
        df = compute_sector_metrics(tickers, raw)
        if df is None or df.empty:
            sig = {"emoji": "⚪", "status": "無資料", "color": "gray", "detail": "無法計算板塊指標"}
        else:
            sig = _signal_from_df(df)
        out.append({"sector": name, "leaders": SECTOR_LEADERS.get(name, []), **sig})
    return _sanitize({"period": period, "signals": out})


def list_sectors() -> list[dict]:
    return [{"name": name, "tickers": tickers, "leaders": SECTOR_LEADERS.get(name, [])}
            for name, tickers in TRACKED_SECTORS.items()]


def get_overview(period: str):
    raw = _get_bulk(period)
    if raw is None or raw.empty:
        return None
    per_sector = {}
    for name, tickers in TRACKED_SECTORS.items():
        df = compute_sector_metrics(tickers, raw)
        if df is not None and not df.empty:
            per_sector[name] = df

    heatmap, rrg, trail, close_series = [], [], [], {}
    for name, df in per_sector.items():
        short = name.split(" ")[0]
        valid_md = df.dropna(subset=["Momentum_Diff"])
        if not valid_md.empty:
            md = _f(valid_md.iloc[-1]["Momentum_Diff"], 2)
            if md is not None:
                heatmap.append({"sector": name, "short": short, "momentum_diff": md, "score": md})
        v = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["RS_Ratio", "RS_Momentum"])
        if not v.empty:
            last = v.iloc[-1]
            rr, rm = _f(last["RS_Ratio"]), _f(last["RS_Momentum"])
            if rr is not None and rm is not None:
                q = rrg_quadrant(rr, rm)
                rrg.append({"sector": name, "short": short, "rs_ratio": _f(rr, 2), "rs_momentum": _f(rm, 2), **q})
                tail = v.iloc[-20:]
                trail.append({"sector": name, "short": short, "color": q["color"],
                              "points": [[_f(r, 3), _f(m, 3)] for r, m in zip(tail["RS_Ratio"], tail["RS_Momentum"])]})
        if "Sector_Close" in df:
            close_series[short] = df["Sector_Close"]

    correlation = None
    if len(close_series) >= 2:
        corr = pd.DataFrame(close_series).pct_change().dropna().corr()
        correlation = {"labels": corr.columns.tolist(),
                       "matrix": [[_f(corr.iloc[i, j], 3) for j in range(len(corr))] for i in range(len(corr))]}

    return _sanitize({"period": period, "heatmap": heatmap, "rrg": rrg, "rrg_trail": trail, "correlation": correlation})


def _f(v, digits=None):
    if v is None:
        return None
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(fv):
        return None
    return round(fv, digits) if digits is not None else fv


def _sanitize(obj):
    """Recursively coerce all numpy scalars and replace inf/-inf/nan with None."""
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        fv = float(obj)
        return None if not np.isfinite(fv) else fv
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    return obj


def _series(s: pd.Series, digits=4):
    return [_f(v, digits) for v in s]


def get_detail(sector: str, period: str):
    if sector not in TRACKED_SECTORS:
        return None
    raw = _get_bulk(period)
    df = compute_sector_metrics(TRACKED_SECTORS[sector], raw)
    if df is None or df.empty:
        return {"sector": sector, "found": False}

    dates = [d.strftime("%Y-%m-%d") for d in df.index]
    # Use last row with valid Sector_Close; today's bar may be NaN if market not closed
    valid_df = df.dropna(subset=["Sector_Close"])
    last = valid_df.iloc[-1] if not valid_df.empty else df.iloc[-1]
    prev_close = (_f(valid_df.iloc[-2]["Sector_Close"]) or 0.0) if len(valid_df) > 1 else 0.0
    cur_close = _f(last["Sector_Close"]) or 0.0
    daily_pct = (cur_close - prev_close) / prev_close * 100 if prev_close else 0.0

    crowd = (_f(last["Crowdedness"]) or 0.0) * 100
    crowd90 = (_f(last["Crowdedness_90p"]) or 0.0) * 100
    overheated = crowd >= crowd90 and crowd90 > 0
    close_v = _f(last["Sector_Close"]) or 0.0
    ma20_v = _f(last["MA20"]) or 0.0
    ma60_v = _f(last["MA60"]) or 0.0
    rs_slope_pct = (_f(last["RS_Slope"]) or 0.0) * 100
    m10 = _f(last["M10"]) or 0.0

    if overheated:
        status = {"level": "error", "text": f"🚨【擁擠度防護罩觸發】資金佔大盤均量比 ({crowd:.2f}%) 突破過去一年 90% 高位 ({crowd90:.2f}%)，散戶情緒擁擠，嚴格執行減碼紀律。"}
    elif close_v < ma20_v:
        status = {"level": "warning", "text": f"🔴【空頭弱勢／跌破月線】指數跌破 20 日均線 ({close_v:.2f} < {ma20_v:.2f})，建議觀望。"}
    elif close_v > ma20_v and ma20_v > ma60_v and rs_slope_pct > 0 and m10 > 0:
        status = {"level": "success", "text": "🟢【強勢多頭排列】Close > MA20 > MA60 且 RS 向上發散，主升段，尋找 VCP 突破建倉最佳時機。"}
    elif close_v > ma20_v and rs_slope_pct > 0:
        status = {"level": "info", "text": "🔵【初步轉強訊號】剛站上 20 日均線且 RS 翻轉向上，留意下方 VCP 潛力股。"}
    else:
        status = {"level": "warning", "text": "🟡【動能衰減／整理區間】月線之上但短線動能減弱或 RS 下滑，可能橫盤消化。"}

    rs_r = _f(last["RS_Ratio"])
    rs_m = _f(last["RS_Momentum"])
    quad = rrg_quadrant(rs_r, rs_m) if rs_r is not None and rs_m is not None else None

    ud = df["UD_DV_Ratio"]
    result = {
        "sector": sector, "found": True, "period": period,
        "leaders": SECTOR_LEADERS.get(sector, []), "tickers": TRACKED_SECTORS[sector],
        "metrics": {
            "daily_pct": _f(daily_pct, 2), "m5": _f(last["M5"], 2),
            "m10": _f(m10, 2), "m20": _f(last["M20"], 2),
            "momentum_diff": _f(last["Momentum_Diff"], 2),
            "rs_slope_pct": _f(rs_slope_pct, 2), "crowd": _f(crowd, 2), "crowd_90p": _f(crowd90, 2),
            "overheated": overheated, "rs_ratio": _f(rs_r, 2), "rs_momentum": _f(rs_m, 2),
            "quadrant": quad, "status": status,
        },
        "chart": {
            "dates": dates,
            # ECharts candlestick 順序: [open, close, low, high]
            "candle": [[_f(o, 3), _f(c, 3), _f(lo, 3), _f(hi, 3)]
                       for o, c, lo, hi in zip(df["Sector_Open"], df["Sector_Close"], df["Sector_Low"], df["Sector_High"])],
            "ma10": _series(df["MA10"]), "ma20": _series(df["MA20"]), "ma60": _series(df["MA60"]),
            "ma120": _series(df["MA120"]), "ma200": _series(df["MA200"]),
            "sector_index": _series(df["Sector_Close"]), "spy_index": _series(df["SPY_Index"]),
            "rs_line": _series(df["RS_Line"]), "breadth": _series(df["Sector_Breadth"], 2),
            "ud_dv": _series(ud, 3), "ud_dv_sma5": _series(ud.rolling(5).mean(), 3),
            "m5_s": _series(df["M5"], 2), "m10_s": _series(df["M10"], 2), "m20_s": _series(df["M20"], 2),
        },
        "vcp": scan_vcp(TRACKED_SECTORS[sector], raw),
    }
    return _sanitize(result)
