"""
backfill_exits.py

Backfills buy_price, exit_price, exit_date, exit_reason, win_loss, days_held
for all historical signals where buy_price is null.

Steps per signal:
  1. Download daily price history from last_date onwards
  2. Set buy_price = next trading day's open after last_date
  3. Walk forward checking stop (2% below entry) / target (7% above) / time (10 days)
  4. Update Supabase row with all exit fields + status

Run once manually:
  python backfill_exits.py
"""

import os
import time
import yfinance as yf
import pandas as pd
from datetime import date
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

# ── Constants ──────────────────────────────────────────────────────────────────
STOP_PCT   = 0.98
TARGET_PCT = 1.07
MAX_DAYS   = 10


def backfill_exits():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment")
        return

    supabase = create_client(supabase_url, supabase_key)

    # Fetch all signals missing buy_price
    response = supabase.table("signals") \
      .select("id, ticker, last_date, buy_price") \
      .is_("buy_price", "null") \
      .eq("has_signal_today", True) \
      .order("last_date", desc=False) \
      .execute()

    signals = response.data
    print(f"Found {len(signals)} signals missing buy_price\n")

    skipped  = 0
    updated  = 0
    failed   = 0

    for i, signal in enumerate(signals, start=1):
        ticker    = signal["ticker"]
        last_date = signal["last_date"]
        sig_id    = signal["id"]

        print(f"[{i}/{len(signals)}] {ticker} ({last_date})", end=" ... ")

        # Download from signal date — need enough days for max hold + buffer
        try:
            df = yf.download(
                ticker,
                start=last_date,
                end=date.today().isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False,
            )
        except Exception as e:
            print(f"download error: {e} — skipping")
            skipped += 1
            continue

        if df is None or df.empty:
            print("no data — skipping")
            skipped += 1
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Row 0 = signal date, Row 1 = entry day (next trading day open)
        if len(df) < 2:
            print("not enough rows for entry — skipping")
            skipped += 1
            continue

        entry_row   = df.iloc[1]
        buy_price   = round(float(entry_row["Open"]), 4)
        stop_price  = round(buy_price * STOP_PCT, 4)
        target_price = round(buy_price * TARGET_PCT, 4)

        if buy_price <= 0:
            print(f"invalid buy_price {buy_price} — skipping")
            skipped += 1
            continue

        # Walk forward from entry day checking exits
        trade_rows = df.iloc[1:].copy()  # entry day onwards

        exit_price  = None
        exit_date   = None
        exit_reason = None
        days_held   = None

        for day_num, (idx, row) in enumerate(trade_rows.iterrows(), start=1):
            day_high  = float(row["High"])
            day_low   = float(row["Low"])
            day_close = float(row["Close"])
            day_date  = idx.date() if hasattr(idx, "date") else idx

            hit_stop   = day_low   <= stop_price
            hit_target = day_high  >= target_price
            hit_time   = day_num   >= MAX_DAYS

            if hit_stop and hit_target:
                # Both same day — conservative: stop wins
                exit_price  = stop_price
                exit_date   = day_date
                exit_reason = "stop"
                days_held   = day_num
                break
            elif hit_stop:
                exit_price  = stop_price
                exit_date   = day_date
                exit_reason = "stop"
                days_held   = day_num
                break
            elif hit_target:
                exit_price  = target_price
                exit_date   = day_date
                exit_reason = "target"
                days_held   = day_num
                break
            elif hit_time:
                exit_price  = day_close
                exit_date   = day_date
                exit_reason = "time"
                days_held   = day_num
                break

        # Build update payload
        update = {"buy_price": buy_price}

        if exit_price is not None:
            win_loss = round((exit_price - buy_price) / buy_price, 4)
            update.update({
                "status":      "closed",
                "exit_price":  exit_price,
                "exit_date":   exit_date.isoformat(),
                "exit_reason": exit_reason,
                "win_loss":    win_loss,
                "days_held":   days_held,
            })
            result_str = f"{exit_reason} on {exit_date} | P&L: {win_loss*100:.2f}% | days: {days_held}"
        else:
            # No exit triggered yet — still open
            update["status"] = "open"
            result_str = "still open"

        try:
            supabase.table("signals").update(update).eq("id", sig_id).execute()
            print(f"buy @ ${buy_price:.2f} | {result_str}")
            updated += 1
        except Exception as e:
            print(f"supabase update failed: {e}")
            failed += 1

        # Small delay to avoid hammering yfinance
        time.sleep(0.3)

    print(f"\n{'='*50}")
    print(f"Done. Updated: {updated} | Skipped: {skipped} | Failed: {failed}")


if __name__ == "__main__":
    backfill_exits()