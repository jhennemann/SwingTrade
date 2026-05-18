"""
backfill_entry_prices.py
Run manually to fill in buy_price for any missed signals on a specific date.
Usage: python backfill_entry_prices.py 2026-05-09
"""

import os
import sys
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()  # loads .env before anything else

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

def get_open_price_for_date(ticker: str, signal_date: str) -> float | None:
    """Fetch the opening price on the day AFTER the signal date (entry day)."""
    try:
        # Entry is next day's open, so we need the day after signal_date
        from datetime import date, timedelta
        entry_date = (date.fromisoformat(signal_date) + timedelta(days=1)).isoformat()

        df = yf.download(
            ticker,
            start=entry_date,
            end=(date.fromisoformat(entry_date) + timedelta(days=4)).isoformat(),  # buffer for weekends
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        if df is None or df.empty:
            print(f"  ⚠️  {ticker}: no data returned")
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        open_price = float(df["Open"].iloc[0])
        return round(open_price, 4)

    except Exception as e:
        print(f"  ❌ {ticker}: error — {e}")
        return None


def backfill(signal_date: str):
    print(f"🔍 Looking for signals from {signal_date} with no buy_price...")

    response = (
        supabase.table("signals")
        .select("id, ticker, last_date")
        .eq("last_date", signal_date)
        .is_("buy_price", "null")
        .execute()
    )

    rows = response.data
    if not rows:
        print("  No signals found (already filled or no signals that day).")
        return

    print(f"  Found {len(rows)} signal(s)\n")

    for row in rows:
        ticker = row["ticker"]
        signal_id = row["id"]

        print(f"  Fetching open price for {ticker}...")
        open_price = get_open_price_for_date(ticker, signal_date)

        if open_price is None:
            print(f"  ⚠️  Skipping {ticker} — could not get open price")
            continue

        supabase.table("signals").update(
            {"buy_price": open_price}
        ).eq("id", signal_id).execute()

        print(f"  ✅ {ticker}: buy_price set to ${open_price:.4f}")

    print("\n✅ Backfill complete.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backfill_entry_prices.py YYYY-MM-DD")
        sys.exit(1)

    backfill(sys.argv[1])