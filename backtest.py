import os

from dotenv import load_dotenv
load_dotenv()


import time
from datetime import date, timedelta
import pandas as pd
import yfinance as yf
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

STOP_LOSS = 0.02
PROFIT_TARGET = 0.07
MAX_DAYS = 10


def get_trading_days(df, start_date, n):
    """Get n trading days after start_date from price dataframe."""
    future = df[df.index.date > start_date]
    return future.head(n)


def simulate_trade(ticker, signal_date):
    try:
        df = yf.download(
            ticker,
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.index = pd.to_datetime(df.index)
        df = df.sort_index()

        # Get next trading day after signal for entry
        future_days = df[df.index.date > signal_date]
        if future_days.empty:
            return None

        entry_day = future_days.iloc[0]
        entry_date = future_days.index[0].date()
        entry_price = float(entry_day["Open"])

        if entry_price <= 0:
            return None

        stop_price = entry_price * (1 - STOP_LOSS)
        target_price = entry_price * (1 + PROFIT_TARGET)

        # Simulate day by day
        trading_days = get_trading_days(df, entry_date, MAX_DAYS + 1)

        exit_price = None
        exit_date = None
        exit_reason = None
        days_held = 0

        for i, (idx, row) in enumerate(trading_days.iterrows()):
            days_held = i + 1
            low = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])

            # Check stop loss
            if low <= stop_price:
                # Exit at next day open
                next_days = df[df.index.date > idx.date()]
                if not next_days.empty:
                    exit_price = float(next_days.iloc[0]["Open"])
                    exit_date = next_days.index[0].date()
                else:
                    exit_price = stop_price
                    exit_date = idx.date()
                exit_reason = "Stop Loss"
                break

            # Check profit target
            if high >= target_price:
                next_days = df[df.index.date > idx.date()]
                if not next_days.empty:
                    exit_price = float(next_days.iloc[0]["Open"])
                    exit_date = next_days.index[0].date()
                else:
                    exit_price = target_price
                    exit_date = idx.date()
                exit_reason = "Profit Target"
                break

            # Check max days
            if days_held >= MAX_DAYS:
                next_days = df[df.index.date > idx.date()]
                if not next_days.empty:
                    exit_price = float(next_days.iloc[0]["Open"])
                    exit_date = next_days.index[0].date()
                else:
                    exit_price = close
                    exit_date = idx.date()
                exit_reason = "Time Exit"
                break

        if exit_price is None or exit_date is None:
            return None

        pnl = (exit_price - entry_price) / entry_price
        win_loss = pnl

        return {
            "Trade ID": f"BT-{ticker}-{signal_date.isoformat()}",
            "Robinhood": ticker,
            "Sector": None,
            "Signal Date": signal_date.isoformat(),
            "Buy Price": round(entry_price, 2),
            "Exit Date": exit_date.isoformat(),
            "Exit Price": round(exit_price, 2),
            "Days Held": days_held,
            "Win/Loss": round(pnl, 6),
            "Exit Reason": exit_reason,
            "Sell By Date": None,
            "Relative Strength": None,
            "Rank": None,
            "Signals in Lookback": None,
            "S&P500 %": None,
            "S&P500 Entry Price": None,
            "S&P500 Exit Price": None,
            "Relative Result": None,
            "One-Line Summary": f"Backtest: {ticker} signal {signal_date.isoformat()} → {exit_reason}",
        }

    except Exception as e:
        print(f"  ⚠ {ticker} ({signal_date}): {e}")
        return None


def main():
    print("=== SwingTrade Backtest ===\n")

    # Fetch all signals from Supabase
    print("Fetching signals from Supabase...")
    response = supabase.table("signals").select("*").eq("has_signal_today", True).execute()
    signals = response.data
    print(f"Found {len(signals)} signals to backtest\n")


    # Get already processed trade IDs to avoid duplicates
    existing = supabase.table("trades").select('"Trade ID"').like('"Trade ID"', 'BT-%').execute()
    existing_ids = set(r['Trade ID'] for r in existing.data)
    print(f"Already processed: {len(existing_ids)} trades\n")

    results = []
    for i, signal in enumerate(signals, start=1):
        ticker = signal["ticker"]
        signal_date = date.fromisoformat(signal["last_date"])

        print(f"[{i}/{len(signals)}] {ticker} — {signal_date}")

        trade_id = f"BT-{ticker}-{signal_date.isoformat()}"
        if trade_id in existing_ids:
            print(f"[{i}/{len(signals)}] {ticker} — skipping (already processed)")
            continue

        trade = simulate_trade(ticker, signal_date)
        if trade:
            # Add RS data from signal
            trade["Relative Strength"] = signal.get("relative_strength")
            trade["Rank"] = signal.get("rank")
            trade["Signals in Lookback"] = signal.get("signals_in_lookback")
            results.append(trade)
            print(f"  ✓ {trade['Exit Reason']} | P&L: {trade['Win/Loss']:.2%}")
        else:
            print(f"  ⚠ Could not simulate")

        # Small delay to avoid rate limiting
        time.sleep(1.5)  # increase from 0.5 to 1.5

    if not results:
        print("\nNo results to push.")
        return

    print(f"\nPushing {len(results)} trades to Supabase...")
    try:
        supabase.table("trades").insert(results).execute()
        print(f"✓ Done! {len(results)} backtest trades inserted.")
    except Exception as e:
        print(f"❌ Failed to insert: {e}")

    # Summary stats
    df = pd.DataFrame(results)
    wins = len(df[df["Win/Loss"] > 0])
    losses = len(df[df["Win/Loss"] <= 0])
    win_rate = wins / len(df) * 100
    avg_pnl = df["Win/Loss"].mean() * 100

    print(f"\n=== Backtest Summary ===")
    print(f"Total trades: {len(df)}")
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Win rate: {win_rate:.1f}%")
    print(f"Avg P&L: {avg_pnl:.2f}%")


if __name__ == "__main__":
    main()