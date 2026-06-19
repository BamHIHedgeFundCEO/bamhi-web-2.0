"""
本機執行：從 EDGAR 抓 Form 4，寫入 Supabase insider_transactions。
用法：python seed_insider.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / "backend" / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_KEY 未設定")
    sys.exit(1)

from supabase import create_client
import edgar
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from itertools import groupby

edgar.set_identity("frank940702@gmail.com")
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE = "insider_transactions"

TYPE_LABEL = {"P": "P-Purchase", "S": "S-Sale", "F": "F-TaxSale"}
BUY_CODES  = {"P"}


def filing_to_txns(f, file_date="", accession_no=""):
    try:
        obj = f.obj()
        df = obj.to_dataframe()
    except Exception as e:
        return []
    if df is None or df.empty:
        return []

    all_codes = {str(r).strip() for r in df["Code"].dropna()}
    has_exercise = bool(all_codes & {"M", "C"})
    txns = []
    for _, row in df.iterrows():
        code = str(row.get("Code", "") or "").strip()
        if code not in {"P", "S", "F"}:
            continue
        shares_raw = row.get("Shares")
        price_raw  = row.get("Price")
        value_raw  = row.get("Value")
        shares = float(shares_raw) if shares_raw is not None and pd.notna(shares_raw) else 0.0
        price  = float(price_raw)  if price_raw  is not None and pd.notna(price_raw)  else 0.0
        value  = float(value_raw)  if value_raw  is not None and pd.notna(value_raw)  else round(shares * price, 2)

        txn_date_raw = row.get("Date", "")
        if hasattr(txn_date_raw, "date"):
            txn_date = txn_date_raw.date().isoformat()
        elif txn_date_raw:
            txn_date = str(txn_date_raw)[:10]
        else:
            txn_date = file_date

        is_exercise_sale = (code == "S" and has_exercise)
        txn_type = "S-ExerciseSale" if is_exercise_sale else TYPE_LABEL.get(code, code)

        txns.append({
            "accession_no": accession_no,
            "symbol": str(row.get("Ticker",   "") or "").strip().upper(),
            "company": str(row.get("Issuer",   "") or "").strip(),
            "reporting_name": str(row.get("Insider",  "") or "").strip(),
            "reporting_role": str(row.get("Position", "") or "").strip(),
            "transaction_type": txn_type,
            "transaction_code": code,
            "is_exercise_sale": is_exercise_sale,
            "shares": shares if code in BUY_CODES else -shares,
            "price": price,
            "amount": abs(value),
            "transaction_date": txn_date,
            "filing_date": file_date,
        })
    return txns


def seed(n=500):
    print(f"Fetching {n} Form 4 filings from EDGAR...")
    filings = list(edgar.get_filings(form="4").head(n))
    print(f"Got {len(filings)} filings. Parsing...")

    cutoff = (date.today() - timedelta(days=90)).isoformat()

    # Check already-inserted accession_nos
    resp = sb.table(TABLE).select("accession_no").execute()
    seen = {r["accession_no"] for r in (resp.data or [])}
    print(f"Already in Supabase: {len(seen)} accession_nos")

    def parse_one(f):
        acc = f.accession_no
        fd  = str(getattr(f, "filing_date", "") or "")[:10]
        if acc in seen:
            return []
        return filing_to_txns(f, fd, acc)

    all_txns = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(parse_one, f): f for f in filings}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                all_txns.extend([t for t in fut.result()
                                  if t.get("transaction_date", "") >= cutoff])
            except Exception:
                pass
            if done % 50 == 0:
                print(f"  parsed {done}/{len(filings)}...")

    print(f"Parsed {len(all_txns)} new transactions. Inserting to Supabase...")

    # Insert per filing (avoids within-batch duplicates)
    all_txns.sort(key=lambda t: t["accession_no"])
    inserted = 0
    for acc_no, group in groupby(all_txns, key=lambda t: t["accession_no"]):
        filing_txns = list(group)
        try:
            sb.table(TABLE).insert(filing_txns).execute()
            inserted += len(filing_txns)
        except Exception as e:
            print(f"  insert error {acc_no}: {e}")

    print(f"Done! {inserted} transactions inserted into Supabase.")


if __name__ == "__main__":
    seed(500)
