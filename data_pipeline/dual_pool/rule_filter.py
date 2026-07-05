"""
rule_filter.py — EDGAR 申報噪音過濾（§6.2）

規則：用 Item 編號先淘汰純行政公告，只把可能含催化劑者送 LLM。
Form 4 直接通過（走規則解析，不過此濾網也不走 LLM）。

設計依據（§6.2）：
  PASS_ITEMS — 可能含催化劑的 8-K Item 集合
  DROP_ITEMS — 純行政公告（無催化劑潛力），直接丟棄
  無 Items 解析到 → 依 8-K 慣例：若主文有實質內容（text 非空）則通過，
                   否則丟棄（避免純附件 8-K 消耗 LLM 配額）
"""

from __future__ import annotations

# ── Item 白名單（可能含催化劑）────────────────────────────────────────
PASS_ITEMS: frozenset[str] = frozenset({
    "1.01",  # 重大協議
    "1.02",  # 重大協議終止（bearish catalyst）
    "1.03",  # 破產/接管
    "2.01",  # 完成收購/處置
    "2.02",  # 業績公布 / guidance
    "2.03",  # 財務義務（可能含債務融資）
    "2.04",  # 加速條款觸發
    "2.05",  # 退出活動成本（重組）
    "2.06",  # 重大減值
    "3.01",  # 下市通知（bearish）
    "3.02",  # 未登記股權出售（dilution）
    "3.03",  # 股東權利修改
    "4.01",  # 換審計師（integrity flag）
    "4.02",  # 財報不可信賴（restatement）
    "5.01",  # 控制權變更
    "5.02",  # 高管異動
    "5.04",  # 暫停交易
    "7.01",  # Reg FD（可能含前瞻信息）
    "8.01",  # 其他（主文有實質內容時通過）
})

# ── Item 黑名單（純行政公告，無催化劑潛力）───────────────────────────
DROP_ITEMS: frozenset[str] = frozenset({
    "1.04",  # 礦場安全
    "5.03",  # 章程修訂（例行）
    "5.05",  # 行為準則（例行）
    "5.06",  # 殼公司狀態
    "5.07",  # 股東表決結果（例行）
    "5.08",  # 董事提名（例行）
    "9.01",  # 財報附件（無獨立催化劑）
})


def filter_filings(filings: list[dict]) -> list[dict]:
    """
    過濾 EDGAR 申報，只保留可能含催化劑者（§6.2）。

    - Form 4：直接通過（走規則解析，省 LLM 配額）
    - 8-K：需至少一個 Item 在 PASS_ITEMS 中；
           或無 Items 但主文非空（可能為不常見 Item 格式）

    回傳通過的申報子集。
    """
    passed: list[dict] = []
    dropped = 0

    for filing in filings:
        form = filing.get("form_type", "")

        if form == "4":
            # Form 4 直接通過，交由 rule_engine 解析交易
            if filing.get("transactions"):
                passed.append(filing)
            else:
                # 無有效交易（如純衍生品 Form 4）→ 略過
                dropped += 1
            continue

        if form != "8-K":
            dropped += 1
            continue

        items = filing.get("items", [])
        text  = filing.get("text", "").strip()

        if not items:
            # 沒解析到 Items：若主文非空視為可能含內容（格式不標準）
            if text:
                passed.append(filing)
            else:
                dropped += 1
            continue

        item_set = set(items)
        has_pass = bool(item_set & PASS_ITEMS)
        only_drop = item_set.issubset(DROP_ITEMS)

        if has_pass and not only_drop:
            passed.append(filing)
        elif only_drop and not has_pass:
            dropped += 1
        else:
            # 混合：有 PASS 就通過
            if has_pass:
                passed.append(filing)
            else:
                dropped += 1

    print(
        f"[rule_filter] 通過 {len(passed)} 份 / "
        f"丟棄 {dropped} 份（共 {len(filings)} 份）"
    )
    return passed
