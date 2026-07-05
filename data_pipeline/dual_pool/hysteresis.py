"""
遲滯機制（§5.6）— 防 churn，維持 watchpool 穩定性

規則摘要：
  進池後保留至少 10 個交易日（以 entered_at 起算）
    → 期間形態條件失守不踢出，但若 adv_dollar 失守標 liquidity_ok=False
  10 日後仍不滿足進池條件 → 移出
  例外立即移出：
    (a) 觸發任一 veto（§7.5）
    (b) adv_dollar 連續 5 個交易日 < $2M
    (c) 左池畢業轉右池
  移出後冷卻 5 個交易日才可重進（防邊界震盪）
  畢業（左→右）不受 10 日保留限制

計算「交易日天數」：直接用日曆日 × 5/7 近似，或以 trading_days_between() 精確計算。
本模組選擇精確計算（傳入 trading_day_set）以符合規格「10 個交易日」語意。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

_HOLD_DAYS    = 10  # 進池後保留最少交易日數
_COOLDOWN_DAYS = 5  # 移出後冷卻交易日數
_LIQUIDITY_VETO_DAYS = 5  # 連續 N 個交易日 adv_dollar < $2M → 立即移出
_ADV_MIN = 2_000_000  # 流動性底線


def trading_days_between(start: date, end: date, trading_day_set: Optional[set] = None) -> int:
    """
    計算 start 到 end 之間的交易日數（含 end，不含 start）。

    若未提供 trading_day_set，以日曆日 × 5/7 近似（誤差 ≤ 1 日）。
    """
    if trading_day_set is None:
        delta = (end - start).days
        return max(0, int(delta * 5 / 7))
    return sum(1 for d in trading_day_set if start < d <= end)


def should_retain(
    ticker: str,
    entered_at: date,
    today: date,
    new_side: str,            # L1 今日判定：'left'|'right'|'discard'
    current_side: str,        # 目前 watchpool 中的 side
    adv_dollar: float,
    low_adv_streak: int,       # 連續 adv_dollar < $2M 交易日數（讀 watchpool.low_adv_streak
                               # rolling counter，由 run_stage1 每日更新：<$2M 加一、≥$2M 歸零）
    veto_triggered: bool = False,
    trading_day_set: Optional[set] = None,
) -> dict:
    """
    判定是否保留此 ticker 在 watchpool。

    回傳：
      {
        "action":       "retain"|"graduate"|"remove",
        "liquidity_ok": bool,
        "reason":       str,
      }

    action 語意：
      retain   → 繼續留在池中（side 不變）
      graduate → 左→右畢業（立即移出左池，以新 side 'right' 重新進入）
      remove   → 移出 watchpool
    """
    held_days = trading_days_between(entered_at, today, trading_day_set)

    # ── 例外立即移出 ──────────────────────────────────────────────────
    if veto_triggered:
        return {"action": "remove", "liquidity_ok": False, "reason": "veto"}

    if low_adv_streak >= _LIQUIDITY_VETO_DAYS:
        return {"action": "remove", "liquidity_ok": False, "reason": "low_adv_streak"}

    # ── 左池畢業（左→右，不受保留限制）─────────────────────────────
    if current_side == "left" and new_side == "right":
        return {"action": "graduate", "liquidity_ok": adv_dollar >= _ADV_MIN, "reason": "graduated_to_right"}

    # ── 保留期內（< 10 交易日）─────────────────────────────────────
    if held_days < _HOLD_DAYS:
        liquidity_ok = adv_dollar >= _ADV_MIN
        return {"action": "retain", "liquidity_ok": liquidity_ok, "reason": f"hold_period({held_days}/{_HOLD_DAYS})"}

    # ── 保留期滿後：檢查是否仍符合當前 side 條件 ─────────────────────
    if new_side == current_side or (current_side == "left" and new_side == "left"):
        return {"action": "retain", "liquidity_ok": adv_dollar >= _ADV_MIN, "reason": "still_qualified"}

    if new_side == "discard":
        return {"action": "remove", "liquidity_ok": False, "reason": "no_longer_qualifies"}

    # right → left 重分類（定案設計）：
    #   右池標的形態退回左側形態 = 動能瓦解退回盤整，走完整 remove + 5 交易日冷卻，
    #   冷卻期滿後若當日仍判左才進左池。刻意「不」無縫轉池——動能失效需冷卻觀察。
    #   與左→右畢業（graduate，立即、不受保留限制）的不對稱是設計行為，非 bug。
    return {"action": "remove", "liquidity_ok": False, "reason": "side_changed"}


def is_cooled_down(
    removed_at: date,
    today: date,
    trading_day_set: Optional[set] = None,
) -> bool:
    """冷卻期已過（≥ 5 交易日）才可重進。"""
    return trading_days_between(removed_at, today, trading_day_set) >= _COOLDOWN_DAYS
