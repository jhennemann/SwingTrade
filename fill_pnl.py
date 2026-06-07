"""
backfill_missed_trades.py

Simulates exits for missed trades that have no exit data and updates Supabase.
"""

import os
from datetime import date, timedelta
from dotenv import load_dotenv
load_dotenv()


import yfinance as yf
import pandas as pd
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MAX_HOLD_DAYS = 30


def simulate_exit(ticker, entry_date, entry_price, stop_price, target_price, max_exit_date):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", auto_adjust=False, progress=False)

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Trading days after entry date
        trading_days = df[df.index.date > date.fromisoformat(entry_date)]
        max_date = date.fromisoformat(max_exit_date)

        exit_price = None
        exit_date = None
        exit_reason = None
        days_held = 0

        for i, (idx, row) in enumerate(trading_days.iterrows(), 1):
            if idx.date() > max_date:
                exit_price = float(row["Open"])
                exit_date = idx.date()
                exit_reason = "time"
                days_held = i
                break

            low = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])

            if low <= stop_price and high >= target_price:
                exit_price = stop_price
                exit_date = idx.date()
                exit_reason = "stop"
                days_held = i
                break
            if low <= stop_price:
                exit_price = stop_price
                exit_date = idx.date()
                exit_reason = "stop"
                days_held = i
                break
            if high >= target_price:
                exit_price = target_price
                exit_date = idx.date()
                exit_reason = "target"
                days_held = i
                break

            if i >= MAX_HOLD_DAYS:
                exit_price = close
                exit_date = idx.date()
                exit_reason = "time"
                days_held = i
                break

        if exit_price is None:
            return None

        pnl_pct = round((exit_price - entry_price) / entry_price * 100, 4)

        return {
            "exit_date": exit_date.isoformat(),
            "exit_price": round(exit_price, 4),
            "exit_reason": exit_reason,
            "days_held": days_held,
            "pnl_pct": pnl_pct,
        }

    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
        return None


def main():
    print("=== Backfill Missed Trades ===\n")

    # Fetch missed trades with no exit data
    response = supabase.table("paper_trades") \
        .select("*") \
        .eq("status", "missed") \
        .is_("exit_date", "null") \
        .execute()

    trades = response.data or []
    print(f"Found {len(trades)} missed trades with no exit data\n")

    if not trades:
        print("Nothing to backfill.")
        return

    updated = 0
    for trade in trades:
        tid = trade["id"]
        ticker = trade["ticker"]
        entry_date = trade["entry_date"]
        entry_price = trade["entry_price"]
        stop_price = trade["stop_price"]
        target_price = trade["target_price"]
        max_exit_date = trade["max_exit_date"]

        print(f"Simulating {tid}...")

        if not all([entry_date, entry_price, stop_price, target_price, max_exit_date]):
            print(f"  ⚠ Missing required fields, skipping")
            continue

        result = simulate_exit(ticker, entry_date, entry_price, stop_price, target_price, max_exit_date)

        if result is None:
            print(f"  ⚠ Could not simulate")
            continue

        supabase.table("paper_trades").update(result).eq("id", tid).execute()
        print(f"  ✓ {result['exit_reason']} | {result['pnl_pct']:+.2f}% | {result['days_held']} days")
        updated += 1

    print(f"\nDone. {updated}/{len(trades)} trades backfilled.")


if __name__ == "__main__":
    main()