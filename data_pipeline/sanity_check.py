"""
data_pipeline/sanity_check.py
資料完整性自動檢核 — 管線跑完後掃 data/*.csv，異常時發 Discord 警報。
原則：sanity check 自己壞掉只 print，絕不 raise 影響主管線。
"""
import os
import glob
import math
import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

# 低頻資料的新鮮度門檻覆蓋（天）：預設 7 天只適用日頻檔
MAX_AGE_OVERRIDES = {
    "gdp_fedfunds_rstar.csv": 120,  # GDP 季頻 + r* 月頻
    "naaim.csv": 14,                # NAAIM 週頻
    "sentiment.csv": 14,            # AAII 週頻
}

# 已知的結構性 NaN（如 ETF 停牌），不重複警報
KNOWN_NAN_COLS = {
    "world_sectors.csv": {"ARS", "GXG"},
}

# ==========================================
# 單檔檢核
# ==========================================
def check_csv(path, date_col=None, max_age_days=7, min_rows=10):
    """
    檢核單一 CSV 檔，回傳問題清單（list[str]）。
    空清單 = 無問題。
    """
    issues = []

    # 1. 檔案存在
    if not os.path.exists(path):
        issues.append("檔案不存在")
        return issues

    # 2. 空檔
    if os.path.getsize(path) == 0:
        issues.append("空檔（0 bytes）")
        return issues

    # 3. 讀入
    try:
        df = pd.read_csv(path)
    except Exception as e:
        issues.append(f"CSV 讀取失敗：{e}")
        return issues

    # 4. 列數
    if len(df) < min_rows:
        issues.append(f"列數過少（{len(df)} < {min_rows}）")

    # 5. 日期新鮮度
    _date_col = date_col
    if _date_col is None:
        # 自動偵測：欄名含 date/Date/日期
        for col in df.columns:
            if any(kw in col for kw in ["date", "Date", "日期"]):
                _date_col = col
                break

    if _date_col and _date_col in df.columns:
        try:
            dates = pd.to_datetime(df[_date_col], errors="coerce").dropna()
            if len(dates) == 0:
                issues.append("[無法驗日期] 日期欄全部解析失敗")
            else:
                latest = dates.max()
                age = (datetime.now() - latest.to_pydatetime().replace(tzinfo=None)).days
                if age > max_age_days:
                    issues.append(f"最新日期過舊（{latest.date()}，距今 {age} 天 > {max_age_days}）")
        except Exception:
            issues.append("[無法驗日期] 日期欄解析例外")
    elif date_col:
        # 使用者指定的欄不存在
        issues.append(f"[無法驗日期] 指定日期欄 '{date_col}' 不存在")

    # 6. 最後一列數值欄 NaN / inf
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols and len(df) > 0:
        last_row = df.iloc[-1][numeric_cols]
        known_nan = KNOWN_NAN_COLS.get(os.path.basename(path), set())
        nan_cols = [c for c in last_row[last_row.isna()].index.tolist() if c not in known_nan]
        inf_cols = [c for c in numeric_cols if not last_row[c] != last_row[c]  # not nan
                    and isinstance(last_row[c], float) and math.isinf(last_row[c])]
        if nan_cols:
            issues.append(f"最後一列含 NaN：{nan_cols[:5]}")  # 最多顯示 5 欄
        if inf_cols:
            issues.append(f"最後一列含 inf：{inf_cols[:5]}")

    return issues


# ==========================================
# Discord 警報（僅管線呼叫時真發；直接執行模組為 dry-run）
# ==========================================
def _send_discord_alert(message, dry_run=False):
    """發送純文字警報至 Discord，dry_run=True 時只 print。"""
    if dry_run:
        print(f"[dry-run] Discord 警報（未實際送出）：\n{message}")
        return

    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    if not webhook_url:
        print("⚠️ 未設定 DISCORD_WEBHOOK，跳過 Discord 通知。")
        return

    try:
        import requests
        payload = {"content": message[:2000]}  # Discord 單訊息上限
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            print("✅ Sanity check 警報已送至 Discord。")
        else:
            print(f"⚠️ Discord 警報送出失敗，狀態碼：{resp.status_code}")
    except Exception as e:
        print(f"⚠️ Discord 警報傳送例外：{e}")


# ==========================================
# 掃全部 CSV
# ==========================================
def run_all(dry_run=False):
    """
    掃 data/*.csv（排除含 Dashboard 的戰報歸檔）。
    dry_run=True → 有問題只 print，不發 Discord（直接執行模組時使用）。
    """
    try:
        pattern = os.path.join(DATA_DIR, "*.csv")
        all_csv = glob.glob(pattern)

        # 排除每日戰報歸檔
        target_files = [f for f in all_csv if "Dashboard" not in os.path.basename(f)]

        if not target_files:
            print("⚠️ sanity_check：找不到任何非戰報 CSV，跳過檢核。")
            return

        all_issues = {}  # {basename: [issue, ...]}

        for fpath in sorted(target_files):
            basename = os.path.basename(fpath)
            try:
                max_age = MAX_AGE_OVERRIDES.get(basename, 7)
                issues = check_csv(fpath, max_age_days=max_age)
            except Exception as e:
                issues = [f"check_csv 例外：{e}"]
            all_issues[basename] = issues

        # Print 逐檔摘要
        print("=" * 42)
        print("📋 Sanity Check 報告")
        print(f"   掃描時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   掃描檔案：{len(target_files)} 個")
        print("-" * 42)
        bad_files = {k: v for k, v in all_issues.items() if v}
        ok_files = [k for k, v in all_issues.items() if not v]
        for fname in ok_files:
            print(f"  ✅ {fname}")
        for fname, issues in bad_files.items():
            for iss in issues:
                print(f"  ❌ {fname}：{iss}")
        print("=" * 42)

        # 有問題 → 發 Discord 警報
        if bad_files:
            lines = ["🚨 **BamHI 資料管線 Sanity Check 警報**"]
            for fname, issues in bad_files.items():
                for iss in issues:
                    lines.append(f"• `{fname}`：{iss}")
            lines.append(f"\n掃描時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
            message = "\n".join(lines)
            if len(message) > 1500:
                message = message[:1470] + "\n…（已截斷）"
            _send_discord_alert(message, dry_run=dry_run)
        else:
            print("✅ 所有資料檔檢核通過，無異常。")

    except Exception as e:
        print(f"⚠️ sanity_check.run_all 例外（不影響管線）：{e}")


# ==========================================
# 直接執行 → dry-run 模式
# ==========================================
if __name__ == "__main__":
    run_all(dry_run=True)
    if "--strict" in sys.argv:
        # strict 模式：有壞檔就以非零碼退出（供 CI 使用）
        _csvs = [f for f in glob.glob(os.path.join(DATA_DIR, "*.csv"))
                 if "Dashboard" not in os.path.basename(f)]
        _any_bad = any(check_csv(f, max_age_days=MAX_AGE_OVERRIDES.get(os.path.basename(f), 7))
                       for f in _csvs)
        sys.exit(1 if _any_bad else 0)
