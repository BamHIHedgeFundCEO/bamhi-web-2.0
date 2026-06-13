"""預先計算板塊輪動資料，存成 JSON 供後端秒讀（避免線上即時下載數百檔股票）。

產出 data/sector_rotation/：
  - overview.json            全覽（熱力圖/RRG/軌跡/相關係數）
  - signals.json             首頁板塊訊號
  - detail_<hash>.json       每個板塊的深度明細（指標/K線/VCP）

本機或 GitHub Actions 執行：python data_pipeline/market/precompute_sector_rotation.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.services import sector_rotation as sr  # noqa: E402

PERIOD = sr.PRECOMPUTE_PERIOD
OUT = sr.PRECOMPUTE_DIR


def _dump(name, data):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  ✓ {name}")


def main():
    os.makedirs(OUT, exist_ok=True)
    print(f"預算板塊輪動 (period={PERIOD})，下載全市場資料中…")

    print("→ overview")
    _dump("overview.json", sr.get_overview(PERIOD))

    print("→ signals")
    _dump("signals.json", sr.get_signals(PERIOD))

    print("→ 各板塊明細")
    for name in sr.TRACKED_SECTORS:
        d = sr.get_detail(name, PERIOD)
        _dump(sr._detail_filename(name), d)

    print("完成 ✅")


if __name__ == "__main__":
    main()
