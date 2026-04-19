"""
price_updater.py
Runs hourly during market hours (9 AM - 4 PM CT, Mon-Fri).
For all open signals within the last 14 days:
  - Fetches current price via yfinance
  - Checks exit conditions (7% target, 2% stop, 10 trading days held)
  - If exit hit: sets status='closed', clears current_price
  - Otherwise: updates current_price and current_price_updated_at
For any signals older than 14 days still showing a price: clears it.
"""

import os
import yfinance as yf
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from supabase import create_client

# ── Supabase ───────────────────────────────────────────────────────────────────
supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"],
)

# ── Constants ──────────────────────────────────────────────────────────────────
TARGET_PCT  =  0.07   # 7% profit target
STOP_PCT    = -0.02   # 2% stop loss
MAX_DAYS    = 14      # calendar day buffer (covers ~10 trading days)


def get_current_price(ticker: str) -> float | None:
    """Fetch the most recent price via the last 1-minute bar."""
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

        # Use the Close of the most recent 1-minute bar
        price = float(df["Close"].iloc[-1])
        return round(price, 4)

    except Exception as e:
        print(f"  ❌ {ticker}: error fetching price — {e}")
        return None


def is_exit_hit(current_price: float, buy_price: float, signal_date: date) -> tuple[bool, str]:
    """
    Returns (should_close, reason).
    Checks target, stop, and max hold period.
    """
    if buy_price and buy_price > 0:
        pct_change = (current_price - buy_price) / buy_price

        if pct_change >= TARGET_PCT:
            return True, f"target hit ({pct_change:+.1%})"

        if pct_change <= STOP_PCT:
            return True, f"stop hit ({pct_change:+.1%})"

    # Max hold: 14 calendar days as a buffer over the 10 trading day rule
    days_held = (date.today() - signal_date).days
    if days_held >= MAX_DAYS:
        return True, f"max hold reached ({days_held} days)"

    return False, ""


def main():
    cutoff = (date.today() - timedelta(days=MAX_DAYS)).isoformat()
    now_utc = datetime.now(timezone.utc).isoformat()

    print(f"📈 Price updater running at {now_utc}")
    print(f"   Fetching open signals since {cutoff}...\n")

    # ── 1. Update open signals ─────────────────────────────────────────────────
    open_response = (
        supabase.table("signals")
        .select("id, ticker, last_date, buy_price, status")
        .eq("status", "open")
        .gte("last_date", cutoff)
        .execute()
    )

    open_rows = open_response.data
    print(f"  Found {len(open_rows)} open signal(s)\n")

    for row in open_rows:
        ticker      = row["ticker"]
        signal_id   = row["id"]
        buy_price   = row.get("buy_price")
        signal_date = date.fromisoformat(row["last_date"])

        print(f"  {ticker} (signal: {signal_date})")

        current_price = get_current_price(ticker)

        if current_price is None:
            print(f"    ⚠️  Skipping — no price data\n")
            continue

        should_close, reason = is_exit_hit(current_price, buy_price, signal_date)

        if should_close:
            supabase.table("signals").update({
                "status": "closed",
                "current_price": None,
                "current_price_updated_at": None,
            }).eq("id", signal_id).execute()
            print(f"    🔴 Closed — {reason}\n")

        else:
            supabase.table("signals").update({
                "current_price": current_price,
                "current_price_updated_at": now_utc,
            }).eq("id", signal_id).execute()
            print(f"    ✅ Updated — ${current_price:.4f}\n")

    # ── 2. Clean up stale open signals older than cutoff ──────────────────────
    stale_response = (
        supabase.table("signals")
        .select("id, ticker")
        .eq("status", "open")
        .lt("last_date", cutoff)
        .not_.is_("current_price", "null")
        .execute()
    )

    stale_rows = stale_response.data
    if stale_rows:
        print(f"  Cleaning up {len(stale_rows)} stale signal(s)...")
        for row in stale_rows:
            supabase.table("signals").update({
                "status": "closed",
                "current_price": None,
                "current_price_updated_at": None,
            }).eq("id", row["id"]).execute()
            print(f"    🔴 {row['ticker']} marked closed (stale)")

    print("\n✅ Price update complete.")


if __name__ == "__main__":
    main()