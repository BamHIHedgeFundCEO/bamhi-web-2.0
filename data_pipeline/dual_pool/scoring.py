"""
scoring.py — L3 計分卡純函式（§7）

stage 5 就緒後：
  1. 還原 §7.4 原始 institution 權重（左 0.20 / 右 0.20）
  2. 把暫移的 catalyst +0.10、narrative +0.10 還原
  3. 移除 data_gap:institution 標記
  4. 把 institution() 函式改為讀 institution_quarterly 表

暫行（stage 3）：institution 恆 0，data_gap 標記，
  權重暫移：左 catalyst 0.30+0.10=0.40 / narrative 0.05+0.10=0.15
            右 catalyst 0.20+0.10=0.30 / narrative 0.20+0.10=0.30
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# ── 權重表（§7.4）— institution 就緒後還原原表 ──────────────────────────
# 左池：institution 0.20 暫移 catalyst +0.10 / narrative +0.10
# 右池：institution 0.20 暫移 catalyst +0.10 / narrative +0.10
WEIGHTS = {
    "left": {
        "catalyst":     0.40,   # §7.4 原 0.30；+0.10 暫代 institution
        "op_leverage":  0.25,
        "institution":  0.00,   # 未就緒，恆 0（§12 底部註記）
        "partnership":  0.10,
        "insider":      0.10,
        "narrative":    0.15,   # §7.4 原 0.05；+0.10 暫代 institution
    },
    "right": {
        "catalyst":     0.30,   # §7.4 原 0.20；+0.10 暫代 institution
        "op_leverage":  0.15,
        "institution":  0.00,
        "partnership":  0.15,
        "insider":      0.10,
        "narrative":    0.30,   # §7.4 原 0.20；+0.10 暫代 institution
    },
}

# counterparty_tier → 乘數（§7.3 / §7.2 partnership）
TIER_MULTIPLIER = {"tier1_giant": 1.3, "tier2": 1.05, "unknown": 1.0}
PARTNERSHIP_SCORE = {"tier1_giant": 1.0, "tier2": 0.6, "unknown": 0.2}

# 板塊 cache 路徑（yfinance info 查詢後 cache 到磁碟）
_DATA_DIR = Path(os.getenv("DUAL_POOL_DATA_DIR", "data/dual_pool"))
_SECTOR_CACHE_FILE = _DATA_DIR / "sector_cache.json"

# rs_rank 快取（sector_rotation 預算好的 signals.json）
_PRECOMPUTE_DIR = Path("data/sector_rotation")
_SIGNALS_FILE   = _PRECOMPUTE_DIR / "signals.json"


# ──────────────────────────────────────────────────────────────────────────
# 輔助：時間
# ──────────────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _days_since(ts_str: str) -> float:
    """計算從 ISO 時間戳到現在的天數（UTC）。"""
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (_utcnow() - ts).total_seconds() / 86400
    except Exception:
        return 9999.0


# ──────────────────────────────────────────────────────────────────────────
# 因子 1：catalyst（§7.3）
# ──────────────────────────────────────────────────────────────────────────

def _one_event(e: dict) -> float:
    """單事件分 one(e)。"""
    spec = e.get("specificity") or 0
    base = spec / 5.0

    tl = e.get("timeline_months")
    if tl is None:
        decay = 1.0
    else:
        decay = max(0.0, 1.0 - tl / 12.0)

    tier_key = e.get("counterparty_tier") or "unknown"
    tier = TIER_MULTIPLIER.get(tier_key, 1.0)

    rec = 1.3 if e.get("is_recurring") else 1.0

    return min(1.0, base * decay * tier * rec)


def factor_catalyst(events: list[dict], score_date: date) -> float:
    """
    catalyst 因子（0-1）。

    active = direction=bullish + 未過期（is_recurring ? 180 : 90 天，以 known_at 計）。
    公式：max(one(e)) + 0.1×(active 事件數-1)，封頂 1.0。

    [v1.1 已知簡化] decay 用抽取當下 timeline_months 固定值，
    不隨時間推進，只有 90/180 天到期懸崖（§7.3）。
    """
    active = []
    for e in events:
        if e.get("direction") != "bullish":
            continue
        known_at = e.get("known_at") or e.get("event_date") or ""
        if not known_at:
            continue
        days_old = _days_since(known_at)
        threshold = 180 if e.get("is_recurring") else 90
        if days_old > threshold:
            continue
        active.append(e)

    if not active:
        return 0.0

    scores = [_one_event(e) for e in active]
    best = max(scores)
    density_bonus = 0.1 * (len(active) - 1)
    return min(1.0, best + density_bonus)


# ──────────────────────────────────────────────────────────────────────────
# 因子 2：institution（§7.2 + §12 stage 5 未就緒）
# ──────────────────────────────────────────────────────────────────────────

def factor_institution() -> float:
    """institution 因子 — stage 5 未就緒，恆 0（§12）。"""
    return 0.0


# ──────────────────────────────────────────────────────────────────────────
# 因子 3：op_leverage（§7.2）
# ──────────────────────────────────────────────────────────────────────────

def _gross_margin_trend_score(gm_history: list[float]) -> float:
    """連續毛利率走揚季數 → 分數。"""
    if len(gm_history) < 2:
        return 0.0
    rising = 0
    for i in range(len(gm_history) - 1, 0, -1):
        if gm_history[i] > gm_history[i - 1]:
            rising += 1
        else:
            break
    if rising == 0:
        return 0.0
    if rising == 1:
        return 0.3
    if rising == 2:
        return 0.7
    return 1.0


def factor_op_leverage(ticker: str, data_gaps: list[str]) -> float:
    """
    op_leverage 因子（0-1）。

    邏輯（§7.2 分段）：
      抓 yfinance 季度財報 ΔEPS% / ΔRev% 與毛利率走揚取 max。
      ΔRev≤0 或 EPS 由負轉正時只用毛利率。
      抓不到 → 0 並記 data_gap:op_leverage。

    回傳值 0-1。
    """
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)

        # 季度財報
        fin = tk.quarterly_financials
        income = tk.quarterly_income_stmt

        score_eps_rev = 0.0
        gm_history = []

        # 毛利率走揚（近 4 季）
        for stmt in [fin, income]:
            if stmt is None or stmt.empty:
                continue
            rows = {str(r).lower() for r in stmt.index}
            # 毛利率 = (Revenue - Cost of Revenue) / Revenue
            rev_row = next((r for r in stmt.index if "total revenue" in str(r).lower() or "revenue" in str(r).lower()), None)
            cog_row = next((r for r in stmt.index if "cost of revenue" in str(r).lower() or "cost of goods sold" in str(r).lower()), None)
            if rev_row and cog_row:
                rev_s = stmt.loc[rev_row].dropna()
                cog_s = stmt.loc[cog_row].dropna()
                common = rev_s.index.intersection(cog_s.index)
                if len(common) >= 2:
                    rev_vals = rev_s[common].sort_index()
                    cog_vals = cog_s[common].sort_index()
                    gm = ((rev_vals - cog_vals) / rev_vals).tolist()
                    gm_history = gm[-4:]  # 最近 4 季
                break

        # ΔEPS% / ΔRev%
        eps_row = None
        rev_row2 = None
        for stmt in [fin, income]:
            if stmt is None or stmt.empty:
                continue
            for r in stmt.index:
                rl = str(r).lower()
                if "diluted eps" in rl or "basic eps" in rl or "earnings per share" in rl:
                    eps_row = r
                if "total revenue" in rl or "total revenues" in rl:
                    rev_row2 = r
            if eps_row and rev_row2:
                break

        if eps_row and rev_row2:
            for stmt in [fin, income]:
                if stmt is None or stmt.empty:
                    continue
                if eps_row in stmt.index and rev_row2 in stmt.index:
                    eps_s = stmt.loc[eps_row].dropna().sort_index()
                    rev_s = stmt.loc[rev_row2].dropna().sort_index()
                    common = eps_s.index.intersection(rev_s.index)
                    if len(common) >= 2:
                        eps_vals = eps_s[common].tolist()
                        rev_vals = rev_s[common].tolist()
                        d_rev = (rev_vals[-1] - rev_vals[-2]) / abs(rev_vals[-2]) if rev_vals[-2] != 0 else 0.0
                        d_eps_pct = (eps_vals[-1] - eps_vals[-2]) / abs(eps_vals[-2]) if eps_vals[-2] != 0 else 0.0
                        eps_neg_to_pos = eps_vals[-2] < 0 <= eps_vals[-1]

                        if d_rev > 0 and not eps_neg_to_pos:
                            ratio = d_eps_pct / d_rev if d_rev != 0 else 0
                            if ratio < 1:
                                score_eps_rev = 0.0
                            elif ratio < 2:
                                score_eps_rev = 0.4
                            elif ratio < 3:
                                score_eps_rev = 0.7
                            else:
                                score_eps_rev = 1.0
                    break

        gm_score = _gross_margin_trend_score(gm_history)
        final = max(score_eps_rev, gm_score)

        if final == 0.0 and not gm_history:
            data_gaps.append("data_gap:op_leverage")

        return final

    except Exception as e:
        print(f"[scoring] op_leverage error for {ticker}: {e}")
        data_gaps.append("data_gap:op_leverage")
        return 0.0


# ──────────────────────────────────────────────────────────────────────────
# 因子 4：partnership（§7.2）
# ──────────────────────────────────────────────────────────────────────────

def factor_partnership(events: list[dict]) -> float:
    """
    partnership 因子（0-1）。

    90 天內 bullish 事件的 counterparty_tier 最高者。
    tier1=1.0 / tier2=0.6 / unknown=0.2；無事件 → 0。
    """
    best = 0.0
    for e in events:
        if e.get("direction") != "bullish":
            continue
        known_at = e.get("known_at") or e.get("event_date") or ""
        if _days_since(known_at) > 90:
            continue
        tier_key = e.get("counterparty_tier") or "unknown"
        score = PARTNERSHIP_SCORE.get(tier_key, 0.2)
        if score > best:
            best = score
    return best


# ──────────────────────────────────────────────────────────────────────────
# 因子 5：insider（§7.2 v1.1）
# ──────────────────────────────────────────────────────────────────────────

def _compute_insider_net_ratio(events: list[dict], market_cap: float) -> Optional[float]:
    """
    近 90 日 Form 4 淨買入金額 / 市值。

    insider_buy/insider_sell 事件的 magnitude_usd 當金額。
    is_dilution_flag=True（10b5-1）的 sell 事件減半計（§7.2）。
    """
    if not market_cap or market_cap <= 0:
        return None

    net = 0.0
    for e in events:
        etype = e.get("event_type") or ""
        known_at = e.get("known_at") or e.get("event_date") or ""
        if _days_since(known_at) > 90:
            continue
        mag = e.get("magnitude_usd") or 0.0
        if etype == "insider_buy":
            net += mag
        elif etype == "insider_sell":
            # 10b5-1 計畫（is_dilution_flag 為代用標記）→ 減半
            factor = 0.5 if e.get("is_dilution_flag") else 1.0
            net -= mag * factor

    return net / market_cap


def factor_insider(
    events: list[dict],
    market_cap: float,
    pool_ratios: list[float],
) -> float:
    """
    insider 因子（0-1）。

    計算自身的淨買入比率，再對同池 pool_ratios 做 percentile（§7.2 v1.1）。
    pool_ratios 是同池所有檔的 net/market_cap 列表（包含自身）。
    """
    ratio = _compute_insider_net_ratio(events, market_cap)
    if ratio is None or not pool_ratios:
        return 0.5  # 缺資料 → 中性

    sorted_ratios = sorted(pool_ratios)
    n = len(sorted_ratios)
    rank = sum(1 for r in sorted_ratios if r <= ratio)
    return rank / n if n > 0 else 0.5


def compute_insider_ratio(events: list[dict], market_cap: float) -> Optional[float]:
    """供 orchestrator 計算各檔比率後建 pool_ratios 列表用。"""
    return _compute_insider_net_ratio(events, market_cap)


# ──────────────────────────────────────────────────────────────────────────
# 因子 6：narrative（§7.2）
# ──────────────────────────────────────────────────────────────────────────

def _load_sector_cache() -> dict:
    """從 data/dual_pool/sector_cache.json 載入 ticker→sector 對映。"""
    if _SECTOR_CACHE_FILE.exists():
        try:
            return json.loads(_SECTOR_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_sector_cache(cache: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _SECTOR_CACHE_FILE.write_text(
            json.dumps(cache, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[scoring] sector_cache save error: {e}")


def _lookup_ticker_sector(ticker: str, cache: dict) -> Optional[str]:
    """從 yfinance info 查 sector，cache 到磁碟。"""
    if ticker in cache:
        return cache[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector") or info.get("sectorKey") or None
        cache[ticker] = sector
        _save_sector_cache(cache)
        return sector
    except Exception as e:
        print(f"[scoring] narrative sector lookup error for {ticker}: {e}")
        return None


def _build_sector_rs_map() -> dict[str, float]:
    """
    從 data/sector_rotation/signals.json 讀板塊 rs_rank 百分位（sector_name → 0-1）。

    signals.json 由 backend/services/sector_rotation.py 預算好，
    格式：{"signals": [{"sector": "...", "rs_ratio": ..., "rs_momentum": ...}, ...]}

    由於直接有 rs_ratio/rs_momentum，取 rs_ratio percentile。
    """
    if not _SIGNALS_FILE.exists():
        return {}
    try:
        data = json.loads(_SIGNALS_FILE.read_text(encoding="utf-8"))
        signals = data.get("signals", [])
        if not signals:
            return {}
        ratios = [s.get("rs_ratio") or 100.0 for s in signals]
        n = len(ratios)
        out = {}
        for s in signals:
            sector = s.get("sector") or ""
            ratio = s.get("rs_ratio") or 100.0
            rank = sum(1 for r in ratios if r <= ratio) / n
            out[sector] = rank
        return out
    except Exception as e:
        print(f"[scoring] narrative rs_map error: {e}")
        return {}


def _match_sector_to_rs(yf_sector: Optional[str], rs_map: dict[str, float]) -> float:
    """
    將 yfinance sector 字串對映到 sector_rotation 板塊名稱。

    sector_rotation 板塊名為中文含英文括號（如「AI 應用軟體 (AI Apps)」），
    用 lower 關鍵字模糊匹配。對不上 → 0.5 中性。
    """
    if not yf_sector or not rs_map:
        return 0.5

    # 關鍵字對映表（yfinance sector → 板塊關鍵字）
    SECTOR_KEYWORDS: dict[str, list[str]] = {
        "Technology":             ["ai", "semiconductor", "software", "tech", "gpu", "cyber"],
        "Healthcare":             ["biotech", "pharma", "medical", "health"],
        "Financial Services":     ["financial", "fintech", "payment"],
        "Energy":                 ["gas", "nuclear", "solar", "uranium", "energy", "electric"],
        "Industrials":            ["defense", "robot", "drone", "grid", "infra"],
        "Basic Materials":        ["copper", "lithium", "rare", "gold", "mineral"],
        "Consumer Cyclical":      ["crypto", "internet", "platform"],
        "Real Estate":            ["data center"],
        "Utilities":              ["utility", "electric"],
        "Communication Services": ["optical", "telecom", "media"],
    }

    yf_lower = yf_sector.lower()
    best_sector = None
    best_score = 0.5

    for key, keywords in SECTOR_KEYWORDS.items():
        if key.lower() in yf_lower:
            # 嘗試在 rs_map 找最佳匹配板塊
            for sector_name, rs_pct in rs_map.items():
                sn_lower = sector_name.lower()
                if any(kw in sn_lower for kw in keywords):
                    if best_sector is None or rs_pct > best_score:
                        best_sector = sector_name
                        best_score = rs_pct
            break

    return best_score


def factor_narrative(
    ticker: str,
    sector_cache: dict,
    rs_map: dict[str, float],
) -> float:
    """
    narrative 因子（0-1）。

    ticker→sector（yfinance info，cache 磁碟）→ 對映 sector_rotation rs_rank percentile/100。
    對不上 → 0.5 中性（§7.2）。
    """
    sector = _lookup_ticker_sector(ticker, sector_cache)
    return _match_sector_to_rs(sector, rs_map)


# ──────────────────────────────────────────────────────────────────────────
# veto（§7.5 + v1.1 時間窗）
# ──────────────────────────────────────────────────────────────────────────

def compute_veto(
    events: list[dict],
    adv_dollar: Optional[float],
    ticker: str,
    data_gaps: list[str],
) -> list[str]:
    """
    計算 veto_flags（§7.5）。

    回傳非空清單 → 不可買（前端標紅）。

    已實作：integrity(365天) / dilution(180天) / cash_runway / liquidity。
    guidance_missed：未就緒（track_record 樣本不足），跳過（§12）。
    """
    flags = []

    # ── integrity：任一 is_integrity_flag=true 事件，近 365 天 ────────────
    for e in events:
        if e.get("is_integrity_flag"):
            if _days_since(e.get("known_at") or e.get("event_date") or "") <= 365:
                flags.append("integrity")
                break

    # ── dilution：任一 is_dilution_flag=true 事件，近 180 天 ─────────────
    for e in events:
        if e.get("is_dilution_flag"):
            if _days_since(e.get("known_at") or e.get("event_date") or "") <= 180:
                flags.append("dilution")
                break

    # ── cash_runway（§7.5 v1.1）─────────────────────────────────────────
    #   TTM operating CF < 0 且 現金/(|TTM opCF|/4) < 2 → veto
    #   缺資料 → 略過並標 data_gap:cash_runway
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        cf = tk.cashflow  # 年報現金流量表

        ttm_opcf = None
        cash = None

        # TTM operating cash flow（取最近年報）
        for r in (cf.index if cf is not None and not cf.empty else []):
            rl = str(r).lower()
            if "operating" in rl and "cash" in rl:
                vals = cf.loc[r].dropna()
                if not vals.empty:
                    ttm_opcf = float(vals.iloc[0])
                break

        # 現金（balance sheet）
        bs = tk.balance_sheet
        for r in (bs.index if bs is not None and not bs.empty else []):
            rl = str(r).lower()
            if "cash and cash equivalents" in rl or "cash equivalents" in rl:
                vals = bs.loc[r].dropna()
                if not vals.empty:
                    cash = float(vals.iloc[0])
                break

        if ttm_opcf is None or cash is None:
            data_gaps.append("data_gap:cash_runway")
        elif ttm_opcf < 0:
            quarterly_burn = abs(ttm_opcf) / 4.0
            if quarterly_burn > 0 and (cash / quarterly_burn) < 2:
                flags.append("cash_runway")

    except Exception as e:
        print(f"[scoring] cash_runway error for {ticker}: {e}")
        data_gaps.append("data_gap:cash_runway")

    # ── liquidity：adv_dollar < $2M ──────────────────────────────────────
    if adv_dollar is not None and adv_dollar < 2_000_000:
        flags.append("liquidity")

    # ── guidance_missed：未就緒，跳過（§12）────────────────────────────
    # TODO stage 5：讀 track_record 表，樣本≥4 且兌現率<0.5 → "guidance_missed"

    return flags


# ──────────────────────────────────────────────────────────────────────────
# Gate（§7.4 v1.1）
# ──────────────────────────────────────────────────────────────────────────

def compute_gate(events: list[dict], side: str) -> bool:
    """
    Gate 判斷（§7.4）— 顯示層過濾，不影響 watchpool 成員資格。

    左池：direction=bullish 且 specificity≥4 且 (timeline_months null 或 ≤6)
    右池：direction=bullish 且 specificity≥3

    [v1.1] Gate 是顯示層第三過濾；候選清單=gate_passed且veto空。
    左池 specificity≥4 在小型股很稀有，候選清單可能常態很短——此為設計行為。
    """
    for e in events:
        if e.get("direction") != "bullish":
            continue
        spec = e.get("specificity") or 0
        if side == "left":
            if spec >= 4:
                tl = e.get("timeline_months")
                if tl is None or tl <= 6:
                    return True
        else:  # right
            if spec >= 3:
                return True
    return False


# ──────────────────────────────────────────────────────────────────────────
# 主計分函式
# ──────────────────────────────────────────────────────────────────────────

def score_ticker(
    ticker: str,
    side: str,
    events: list[dict],
    adv_dollar: Optional[float],
    market_cap: Optional[float],
    pool_insider_ratios: list[float],
    sector_cache: dict,
    rs_map: dict[str, float],
    score_date: date,
) -> dict:
    """
    計算一檔的完整 L3 分數。

    回傳 dict 對應 §3.3 scores schema：
      ticker, score_date, side, total,
      catalyst, institution, op_leverage, partnership, insider, narrative,
      gate_passed, veto_flags, data_gaps
    """
    data_gaps: list[str] = []

    # 各因子
    f_catalyst    = factor_catalyst(events, score_date)
    f_institution = factor_institution()                         # 恆 0（stage 5）
    f_op_leverage = factor_op_leverage(ticker, data_gaps)
    f_partnership = factor_partnership(events)
    f_insider     = factor_insider(events, market_cap or 0.0, pool_insider_ratios)
    f_narrative   = factor_narrative(ticker, sector_cache, rs_map)

    data_gaps.append("data_gap:institution")  # §12 stage 5 未就緒

    # 加權和
    w = WEIGHTS[side]
    total_raw = (
        w["catalyst"]    * f_catalyst
        + w["institution"] * f_institution
        + w["op_leverage"] * f_op_leverage
        + w["partnership"] * f_partnership
        + w["insider"]     * f_insider
        + w["narrative"]   * f_narrative
    )
    total = round(total_raw * 100, 2)

    # veto
    veto_flags = compute_veto(events, adv_dollar, ticker, data_gaps)

    # gate
    gate_passed = compute_gate(events, side)

    return {
        "ticker":       ticker,
        "score_date":   score_date.isoformat(),
        "side":         side,
        "total":        total,
        "catalyst":     round(f_catalyst, 4),
        "institution":  round(f_institution, 4),
        "op_leverage":  round(f_op_leverage, 4),
        "partnership":  round(f_partnership, 4),
        "insider":      round(f_insider, 4),
        "narrative":    round(f_narrative, 4),
        "gate_passed":  gate_passed,
        "veto_flags":   veto_flags,
        "data_gaps":    list(set(data_gaps)),
    }
