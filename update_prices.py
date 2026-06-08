"""
price_updater.py

Fetches current prices for all open paper trades and updates
current_price, pnl_pct, and days_held in Supabase.
Runs every 15 minutes during market hours via GitHub Actions.
"""

import os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

import yfinance as yf
import pandas as pd
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def main():
    print("=== Update Open Trade Prices ===\n")

    response = supabase.table("paper_trades") \
        .select("id, ticker, entry_price, entry_date") \
        .eq("status", "open") \
        .execute()

    trades = response.data or []
    print(f"Found {len(trades)} open trades\n")

    if not trades:
        print("Nothing to update.")
        return

    # Fetch unique tickers in one batch
    tickers = list(set(t["ticker"] for t in trades))
    print(f"Fetching prices for: {', '.join(tickers)}")

    prices = {}
    for ticker in tickers:
        try:
            data = yf.download(ticker, period="2d", interval="1d", auto_adjust=False, progress=False)
            if data is not None and not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                prices[ticker] = float(data["Close"].iloc[-1])
                print(f"  {ticker}: ${prices[ticker]:.2f}")
        except Exception as e:
            print(f"  ⚠ {ticker}: {e}")

    # Update each trade
    updated = 0
    today = date.today()

    for trade in trades:
        ticker = trade["ticker"]
        entry_price = trade.get("entry_price")
        entry_date = trade.get("entry_date")
        price = prices.get(ticker)

        if price is None:
            print(f"  ⚠ No price for {ticker}, skipping")
            continue

        pnl_pct = round((price - entry_price) / entry_price * 100, 4) if entry_price else None
        days_held = (today - date.fromisoformat(entry_date)).days if entry_date else None

        supabase.table("paper_trades") \
            .update({
                "current_price": round(price, 4),
                "pnl_pct": pnl_pct,
                "days_held": days_held,
            }) \
            .eq("id", trade["id"]) \
            .execute()

        print(f"  ✓ {ticker}: ${price:.2f} | {pnl_pct:+.2f}% | {days_held} days")
        updated += 1

    print(f"\nDone. {updated}/{len(trades)} trades updated.")


if __name__ == "__main__":
    main()