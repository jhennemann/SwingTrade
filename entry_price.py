"""
entry_price.py
Runs once each morning at ~9:45 AM CT (after open settles).
Finds signals from yesterday with no buy_price yet, fetches the
first 1-minute bar open as the entry price, upserts back to Supabase.
"""

import os
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from supabase import create_client

# ── Supabase ───────────────────────────────────────────────────────────────────
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)


def get_open_price(ticker: str) -> float | None:
    """Fetch today's opening price via the first 1-minute bar."""
    try:
        df = yf.download(
            ticker,
            period="1d",
            interval="1m",
            auto_adjust=False,
            progress=False,
        )

        if df is None or df.empty:
            print(f"  ⚠️  {ticker}: no intraday data returned")
            return None

        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        open_price = float(df["Open"].iloc[0])
        return round(open_price, 4)

    except Exception as e:
        print(f"  ❌ {ticker}: error fetching open price — {e}")
        return None


def main():
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    print(f"🔍 Looking for signals from {yesterday} with no buy_price...")

    # Fetch signals from yesterday that don't have a buy_price yet
    response = (
        supabase.table("signals")
        .select("id, ticker, last_date")
        .eq("last_date", yesterday)
        .is_("buy_price", "null")
        .execute()
    )

    rows = response.data
    if not rows:
        print("  No signals need an entry price today.")
        return

    print(f"  Found {len(rows)} signal(s) to update\n")

    for row in rows:
        ticker = row["ticker"]
        signal_id = row["id"]

        print(f"  Fetching open price for {ticker}...")
        open_price = get_open_price(ticker)

        if open_price is None:
            print(f"  ⚠️  Skipping {ticker} — could not get open price")
            continue

        # Upsert buy_price back to signals row
        supabase.table("signals").update(
            {"buy_price": open_price}
        ).eq("id", signal_id).execute()

        print(f"  ✅ {ticker}: buy_price set to ${open_price:.4f}")

    print("\n✅ Entry price update complete.")


if __name__ == "__main__":
    main()