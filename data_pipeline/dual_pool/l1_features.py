"""
L1 形態識別 — 本地計算（yfinance）

★ 形態事實（§5.2，必讀）：
  長期盤整剛翻上時，價格是「穿過」低位糾纏的長均線群往上，不是待在它們下面。
  因此「價格 ≤ MA120/MA200」是錯的左側判別子 —— 那是「還沒拐頭」的過早階段。
  真正的判別子是：長均線糾纏度 + 長均線走平 + 距52週低近 + 已收復短均線（reclaimed_short）。

★ 互斥保證（§5.6，必讀）：
  entangle=0.06 恰好同時滿足左池 ≤0.06 與右池 ≥0.06。
  左右互斥靠「先判左、再判右」的順序保證，不是條件本身保證。
  改判定順序 = 改行為，嚴禁。

★ CAGR 閘門（§5.5）：
  右池可選，預設關閉（enable_cagr_gate=False）。
  左池永不套用（RKLB/NBIS 型標的進場時無 5 年 CAGR）。
  歷史不足 5 年 → 視為通過（不誤殺近年 IPO/SPAC）。
"""

from __future__ import annotations

import warnings
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)

# ── L1 特徵定義（§5.1） ───────────────────────────────────────────────
_HIST_DAYS      = 400   # 至少拉 400 個交易日
_MIN_HIST_DAYS  = 200   # 歷史不足 200 日 → 資料不足，丟棄

# 左池門檻（§5.3）
LEFT_THRESHOLDS = {
    "adv_dollar":       2_000_000,  # ≥ $2M（流動性底線）
    "reclaimed_short":  True,       # 已站上 MA5+MA20（崩盤地板，不可關）
    "entangle":         0.06,       # ≤ 0.06（長均線糾纏）
    "slope200":         -0.02,      # ≥ -0.02（長均線走平）
    "dist_low":         0.40,       # ≤ 40%（仍在底部區）
    "ext":              0.25,       # ≤ 25%（未過度延伸）
    "vol_ratio":        2.0,        # ≤ 2.0（量能溫和）
}

# 右池門檻（§5.4）
RIGHT_THRESHOLDS = {
    "adv_dollar":   2_000_000,  # ≥ $2M
    "bull_align":   True,       # 多頭排列已成
    "entangle":     0.06,       # ≥ 0.06（長均線發散）
    "dist_low":     0.30,       # ≥ 30%（已離開底部）
    "slope200":     0.015,      # ≥ 1.5%（長均線上揚）
    "vol_ratio":    1.2,        # ≥ 1.2（突破帶量）
}

# 右池 CAGR 閘門（§5.5，預設關閉）
CAGR_MIN_REV = 0.15   # 5年營收 CAGR ≥ 15%
CAGR_MIN_EPS = 0.10   # 5年 EPS CAGR ≥ 10%


# ── 特徵計算 ─────────────────────────────────────────────────────────

def compute_features(hist: pd.DataFrame) -> Optional[dict]:
    """
    輸入 yfinance 拉回的歷史 OHLCV（auto_adjust=True，DatetimeIndex），
    回傳特徵字典；歷史不足 200 日回傳 None（資料不足丟棄）。

    hist 欄位：Open / High / Low / Close / Volume（auto_adjust 後已複權）
    """
    if hist is None or hist.empty:
        return None

    # 防線：yfinance 1.2+ 單檔下載/舊 cache 可能帶 MultiIndex 欄位
    # （('Close','AAPL')），攤平確保 hist["Close"] 為 Series 而非 DataFrame。
    if isinstance(hist.columns, pd.MultiIndex):
        hist = hist.copy()
        hist.columns = hist.columns.get_level_values(0)

    close = hist["Close"].dropna()
    if len(close) < _MIN_HIST_DAYS:
        return None

    vol   = hist["Volume"].reindex(close.index).fillna(0)

    # ── MA 系列 ──────────────────────────────────────────────────────
    ma5   = close.rolling(5).mean()
    ma20  = close.rolling(20).mean()
    ma60  = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()
    ma200 = close.rolling(200).mean()

    # 最新值
    price    = float(close.iloc[-1])
    ma5_v    = float(ma5.iloc[-1])
    ma20_v   = float(ma20.iloc[-1])
    ma60_v   = float(ma60.iloc[-1])
    ma120_v  = float(ma120.iloc[-1])
    ma200_v  = float(ma200.iloc[-1])
    ma200_20 = float(ma200.iloc[-21]) if len(ma200.dropna()) >= 21 else ma200_v

    if any(np.isnan(v) for v in [ma5_v, ma20_v, ma60_v, ma120_v, ma200_v]):
        return None

    # ── 糾纏度 entangle（§5.1）────────────────────────────────────────
    long_mas = [ma60_v, ma120_v, ma200_v]
    entangle = (max(long_mas) - min(long_mas)) / np.mean(long_mas)

    # ── slope200：近 20 日 MA200 斜率（§5.1）─────────────────────────
    slope200 = (ma200_v - ma200_20) / ma200_20 if ma200_20 != 0 else 0.0

    # ── 52 週最高/最低（§5.1）─────────────────────────────────────────
    year_close = close.iloc[-252:] if len(close) >= 252 else close
    hi52  = float(year_close.max())
    lo52  = float(year_close.min())

    dist_low  = (price - lo52) / lo52  if lo52  != 0 else 0.0
    dist_high = (hi52 - price)  / hi52  if hi52  != 0 else 0.0

    # ── 延伸度 ext（§5.1）────────────────────────────────────────────
    ext = price / ma200_v - 1.0

    # ── 成交額 adv_dollar（§5.1，近 20 日均值）────────────────────────
    dollar_vol   = close * vol
    adv_dollar   = float(dollar_vol.iloc[-20:].mean()) if len(dollar_vol) >= 20 else float(dollar_vol.mean())

    # ── 量比 vol_ratio（§5.1）────────────────────────────────────────
    avg5  = float(vol.iloc[-5:].mean())   if len(vol) >= 5  else float(vol.mean())
    avg60 = float(vol.iloc[-60:].mean())  if len(vol) >= 60 else float(vol.mean())
    vol_ratio = avg5 / avg60 if avg60 > 0 else 1.0

    # ── 派生布林 ──────────────────────────────────────────────────────
    reclaimed_short = bool(price > ma5_v and price > ma20_v)
    bull_align      = bool(ma5_v > ma20_v > ma60_v > ma120_v > ma200_v)

    return {
        "price":           price,
        "ma5":             ma5_v,
        "ma20":            ma20_v,
        "ma60":            ma60_v,
        "ma120":           ma120_v,
        "ma200":           ma200_v,
        "entangle":        round(entangle, 6),
        "slope200":        round(slope200, 6),
        "dist_low":        round(dist_low, 4),
        "dist_high":       round(dist_high, 4),
        "ext":             round(ext, 4),
        "adv_dollar":      round(adv_dollar, 2),
        "vol_ratio":       round(vol_ratio, 4),
        "reclaimed_short": reclaimed_short,
        "bull_align":      bull_align,
    }


# ── 池判定 ────────────────────────────────────────────────────────────

def classify(features: dict, enable_cagr_gate: bool = False,
             cagr_rev: Optional[float] = None,
             cagr_eps: Optional[float] = None) -> str:
    """
    依特徵判定分池，回傳 'left' | 'right' | 'discard'。

    ★ 互斥保證靠先判左的順序（§5.6）：
      entangle=0.06 邊界兩側條件可同時滿足，先判左確保邊界落入左池。
      改判定順序 = 改行為。

    ★ CAGR 閘門（§5.5）：
      左池永不套用；右池預設關閉。
      enable_cagr_gate=True 時，cagr_rev/cagr_eps 若為 None 視為歷史不足 → 通過。
    """
    f = features
    L = LEFT_THRESHOLDS
    R = RIGHT_THRESHOLDS

    # ── 先判左池（§5.3）──────────────────────────────────────────────
    is_left = (
        f["adv_dollar"]       >= L["adv_dollar"]       and
        f["reclaimed_short"]  == L["reclaimed_short"]  and
        f["entangle"]         <= L["entangle"]          and
        f["slope200"]         >= L["slope200"]          and
        f["dist_low"]         <= L["dist_low"]          and
        f["ext"]              <= L["ext"]               and
        f["vol_ratio"]        <= L["vol_ratio"]
    )
    if is_left:
        return "left"

    # ── 再判右池（§5.4）──────────────────────────────────────────────
    is_right = (
        f["adv_dollar"]  >= R["adv_dollar"]  and
        f["bull_align"]  == R["bull_align"]  and
        f["entangle"]    >= R["entangle"]    and
        f["dist_low"]    >= R["dist_low"]    and
        f["slope200"]    >= R["slope200"]    and
        f["vol_ratio"]   >= R["vol_ratio"]
    )
    if not is_right:
        return "discard"

    # ── 右池可選 CAGR 閘門（§5.5，預設關閉）─────────────────────────
    if enable_cagr_gate:
        # 歷史不足 5 年（None）→ 視為通過，不誤殺近年 IPO/SPAC
        if cagr_rev is not None and cagr_rev < CAGR_MIN_REV:
            return "discard"
        if cagr_eps is not None and cagr_eps < CAGR_MIN_EPS:
            return "discard"

    return "right"


def compute_market_cap(info: dict) -> Optional[float]:
    """從 yfinance info 提取市值。"""
    return info.get("marketCap") or info.get("enterpriseValue")


def process_ticker(
    ticker: str,
    hist: pd.DataFrame,
    info: Optional[dict] = None,
    enable_cagr_gate: bool = False,
) -> dict:
    """
    對單一 ticker 計算 L1 特徵並分池。

    回傳：
      {
        "ticker": str,
        "side": "left"|"right"|"discard"|"insufficient_data"|"error",
        "features": dict | None,
        "market_cap": float | None,
      }
    """
    try:
        features = compute_features(hist)
        if features is None:
            return {"ticker": ticker, "side": "insufficient_data", "features": None, "market_cap": None}

        # CAGR 閘門資料（暫不計算，預設關閉；開啟時需另行從 yfinance financials 算）
        side = classify(features, enable_cagr_gate=enable_cagr_gate)

        market_cap = None
        if info:
            market_cap = compute_market_cap(info)

        return {
            "ticker":     ticker,
            "side":       side,
            "features":   features,
            "market_cap": market_cap,
        }
    except Exception as e:
        return {"ticker": ticker, "side": "error", "features": None, "market_cap": None, "error": str(e)}
