"""
update_data.py - 數據更新總指揮
"""
import data_pipeline.rates as rates_dept
import data_pipeline.market as market_dept
import data_pipeline.sanity_check as sanity_check

def main():
    print("==========================================")
    print("🚀 BamHI 數據流水線 (Data Pipeline) 啟動")
    print("==========================================")

    # 1. 叫利率部門做事
    try:
        rates_dept.update()
    except Exception as e:
        print(f"❌ 利率部門回報錯誤: {e}")

    print("-" * 30)

    # 2. 叫市場部門做事
    try:
        market_dept.update()
    except Exception as e:
        print(f"❌ 市場部門回報錯誤: {e}")

    print("==========================================")
    print("✅ 所有任務執行完畢！")

    # 3. 資料完整性自動檢核（有問題發 Discord 警報；自己壞掉只 print）
    print("-" * 30)
    try:
        sanity_check.run_all(dry_run=False)
    except Exception as e:
        print(f"⚠️ sanity_check 例外（不影響管線）：{e}")

if __name__ == "__main__":
    main()