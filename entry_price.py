"""
entry_price.py
Runs once each morning at ~9:45 AM CT (after open settles).

1. Finds pullback signals from yesterday with no buy_price yet,
   fetches the first 1-minute bar open as the entry price.

2. Finds paper trades with status='pending', fetches today's open
   price and converts them to status='open' with full entry data.
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


def get_last_trading_day() -> date:
    """Return the most recent weekday (skips weekends)."""
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


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
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return round(float(df["Open"].iloc[0]), 4)
    except Exception as e:
        print(f"  ❌ {ticker}: error fetching open price — {e}")
        return None


# ── Part 1: Pullback signal entry prices ──────────────────────────────────────

def update_pullback_entry_prices():
    yesterday = get_last_trading_day().isoformat()
    print(f"🔍 Looking for pullback signals from {yesterday} with no buy_price...")

    response = (
        supabase.table("signals")
        .select("id, ticker, last_date")
        .eq("last_date", yesterday)
        .is_("buy_price", "null")
        .execute()
    )

    rows = response.data
    if not rows:
        print("  No pullback signals need an entry price today.")
        return

    print(f"  Found {len(rows)} signal(s) to update\n")

    for row in rows:
        ticker    = row["ticker"]
        signal_id = row["id"]

        print(f"  Fetching open price for {ticker}...")
        open_price = get_open_price(ticker)

        if open_price is None:
            print(f"  ⚠️  Skipping {ticker} — could not get open price")
            continue

        supabase.table("signals").update(
            {"buy_price": open_price}
        ).eq("id", signal_id).execute()

        print(f"  ✅ {ticker}: buy_price set to ${open_price:.4f}")


# ── Part 2: Paper trade pending → open ────────────────────────────────────────

def update_paper_trade_entries():
    print(f"\n🔍 Looking for pending paper trades to activate...")

    response = (
        supabase.table("paper_trades")
        .select("*")
        .eq("status", "pending")
        .execute()
    )

    rows = response.data
    if not rows:
        print("  No pending paper trades to activate.")
        return

    print(f"  Found {len(rows)} pending trade(s)\n")

    for trade in rows:
        ticker       = trade["ticker"]
        trade_id     = trade["id"]
        config       = trade["config"]
        position_size = float(trade["position_size"])

        print(f"  Fetching open price for {ticker} [{config}]...")
        entry_price = get_open_price(ticker)

        if entry_price is None:
            print(f"  ⚠️  Skipping {ticker} — could not get open price, stays pending")
            continue

        # Calculate all entry fields now that we have the real open price
        cfg = {
            "conservative": {"stop_pct": 0.02, "target_pct": 0.07, "max_days": 10},
            "aggressive":   {"stop_pct": 0.02, "target_pct": 0.15, "max_days": 20},
        }[config]

        stop_price   = round(entry_price * (1 - cfg["stop_pct"]),   4)
        target_price = round(entry_price * (1 + cfg["target_pct"]), 4)
        shares       = round(position_size / entry_price,            6)
        cost_basis   = round(shares * entry_price,                   2)

        # max_exit_date: signal_date + max_days trading days from today
        entry_date = date.today()
        max_exit   = _add_trading_days(entry_date, cfg["max_days"])

        supabase.table("paper_trades").update({
            "status":       "open",
            "entry_date":   entry_date.isoformat(),
            "entry_price":  entry_price,
            "stop_price":   stop_price,
            "target_price": target_price,
            "max_exit_date": max_exit.isoformat(),
            "shares":       shares,
            "cost_basis":   cost_basis,
        }).eq("id", trade_id).execute()

        print(
            f"  ✅ {ticker} [{config}]: activated @ ${entry_price:.2f} | "
            f"stop ${stop_price:.2f} | target ${target_price:.2f} | "
            f"{shares:.4f} shares"
        )


def _add_trading_days(from_date: date, n: int) -> date:
    d = from_date
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"=== Entry Price Updater — {date.today().isoformat()} ===\n")

    update_pullback_entry_prices()
    update_paper_trade_entries()

    print("\n✅ Entry price update complete.")


if __name__ == "__main__":
    main()