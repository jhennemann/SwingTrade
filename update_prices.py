"""
update_prices.py

Fetches intraday prices for all open paper trades, checks stop/target/time exits,
and updates Supabase accordingly. Runs every 15 minutes during market hours via GitHub Actions.
"""

import os
from datetime import date, datetime
from dotenv import load_dotenv
load_dotenv()

import yfinance as yf
import pandas as pd
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_intraday(ticker):
    """Fetch today's 1-minute bars for a ticker. Returns DataFrame or None."""
    try:
        data = yf.download(ticker, period="1d", interval="1m", auto_adjust=False, progress=False)
        if data is None or data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        print(f"  ⚠ {ticker}: download failed — {e}")
        return None


def check_exit(trade, df):
    """
    Check intraday bars against stop/target/time thresholds.
    Returns (exit_price, exit_reason) or (None, None) if still open.
    """
    stop_price   = trade.get("stop_price")
    target_price = trade.get("target_price")
    max_exit_date = trade.get("max_exit_date")
    entry_date   = trade.get("entry_date")

    today = date.today()

    # Time exit — max_exit_date reached
    if max_exit_date and today >= date.fromisoformat(max_exit_date):
        last_close = float(df["Close"].iloc[-1])
        return round(last_close, 4), "time"

    for _, row in df.iterrows():
        day_high = float(row["High"])
        day_low  = float(row["Low"])

        hit_stop   = stop_price   and day_low  <= stop_price
        hit_target = target_price and day_high >= target_price

        if hit_stop and hit_target:
            # Both hit same bar — assume stop (conservative)
            return round(stop_price, 4), "stop"
        elif hit_stop:
            return round(stop_price, 4), "stop"
        elif hit_target:
            return round(target_price, 4), "target"

    return None, None


def main():
    print("=== Update Open Trade Prices ===\n")

    response = supabase.table("paper_trades") \
        .select("id, config, ticker, entry_price, entry_date, stop_price, target_price, max_exit_date, position_size") \
        .eq("status", "open") \
        .execute()

    trades = response.data or []
    print(f"Found {len(trades)} open trades\n")

    if not trades:
        print("Nothing to update.")
        return

    # Fetch unique tickers
    tickers = list(set(t["ticker"] for t in trades))
    print(f"Fetching intraday data for: {', '.join(tickers)}\n")

    intraday = {}
    for ticker in tickers:
        df = fetch_intraday(ticker)
        if df is not None:
            intraday[ticker] = df
            print(f"  {ticker}: {len(df)} bars fetched")
        else:
            print(f"  ⚠ {ticker}: no data")

    today = date.today()
    updated = 0
    exited = 0

    for trade in trades:
        ticker      = trade["ticker"]
        entry_price = trade.get("entry_price")
        entry_date  = trade.get("entry_date")
        position_size = trade.get("position_size")
        df = intraday.get(ticker)

        if df is None:
            print(f"  ⚠ {ticker}: skipping — no intraday data")
            continue

        current_price = round(float(df["Close"].iloc[-1]), 4)
        pnl_pct       = round((current_price - entry_price) / entry_price * 100, 4) if entry_price else None
        pnl_dollars   = round((current_price - entry_price) / entry_price * position_size, 2) if entry_price and position_size else None
        days_held     = (today - date.fromisoformat(entry_date)).days if entry_date else None

        exit_price, exit_reason = check_exit(trade, df)

        if exit_reason:
            final_pnl_pct     = round((exit_price - entry_price) / entry_price * 100, 4) if entry_price else None
            final_pnl_dollars = round((exit_price - entry_price) / entry_price * position_size, 2) if entry_price and position_size else None

            supabase.table("paper_trades").update({
                "status":      "closed",
                "exit_price":  exit_price,
                "exit_date":   today.isoformat(),
                "exit_reason": exit_reason,
                "pnl_pct":     final_pnl_pct,
                "pnl_dollars": final_pnl_dollars,
                "days_held":   days_held,
                "current_price": exit_price,
            }).eq("id", trade["id"]).execute()

            print(f"  ✓ {ticker} [{trade['config']}]: CLOSED via {exit_reason} | exit ${exit_price:.2f} | P&L: {final_pnl_pct:+.2f}%")
            exited += 1
        else:
            supabase.table("paper_trades").update({
                "current_price": current_price,
                "pnl_pct":       pnl_pct,
                "pnl_dollars":   pnl_dollars,
                "days_held":     days_held,
            }).eq("id", trade["id"]).execute()

            print(f"  ✓ {ticker} [{trade['config']}]: ${current_price:.2f} | {pnl_pct:+.2f}% | {days_held}d")
            updated += 1

    print(f"\nDone. {updated} updated, {exited} closed.")


if __name__ == "__main__":
    main()