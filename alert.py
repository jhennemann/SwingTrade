import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime, date
from src.exit_rules import SimpleExitRules
from supabase import create_client

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not DISCORD_WEBHOOK:
    raise RuntimeError("Missing DISCORD_WEBHOOK_URL")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing Supabase credentials")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

exit_rules = SimpleExitRules(
    stop_loss_pct=0.02,
    profit_target_pct=0.07,
    max_hold_days=10
)


def send_discord_alert(message: str):
    chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
    for chunk in chunks:
        requests.post(DISCORD_WEBHOOK, json={"content": chunk}, timeout=10).raise_for_status()
    print("✅ Alert sent to Discord")


def get_trading_days_held(signal_date: date) -> int:
    """Count actual trading days between signal date and today."""
    df = yf.download("SPY", start=signal_date, end=date.today(), progress=False)
    return len(df)


def auto_log_buys():
    """
    For signals fired yesterday with no trades row yet,
    fetch yesterday's close as a proxy for today's open and insert a trade.
    """
    yesterday = pd.Timestamp.now().normalize() - pd.offsets.BDay(1)
    yesterday_str = yesterday.strftime("%Y-%m-%d")

    # Get signals from yesterday that have no trade logged
    res = supabase.table("signals") \
        .select("ticker, last_date") \
        .eq("last_date", yesterday_str) \
        .eq("has_signal_today", True) \
        .execute()

    if not res.data:
        print("No new signals to auto-log")
        return

    for row in res.data:
        ticker = row["ticker"]
        signal_date = row["last_date"]

        # Check if trade already exists
        existing = supabase.table("trades") \
            .select("id") \
            .eq("Robinhood", ticker) \
            .eq("Signal Date", signal_date) \
            .execute()

        if existing.data:
            print(f"  {ticker} already has a trade row, skipping")
            continue

        # Fetch today's open as buy price
        df = yf.download(ticker, period="2d", interval="1d",
                         auto_adjust=False, progress=False)
        if df is None or df.empty:
            print(f"  ⚠️ {ticker}: no price data")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        buy_price = float(df["Open"].iloc[-1])
        sell_by = (pd.Timestamp(signal_date) + pd.offsets.BDay(10)).strftime("%Y-%m-%d")

        trade_id = f"AT-{ticker}-{signal_date}"  # AT = auto-trade

        supabase.table("trades").insert({
            "Trade ID": trade_id,
            "Robinhood": ticker,
            "Signal Date": signal_date,
            "Buy Price": buy_price,
            "Sell By Date": sell_by,
        }).execute()

        print(f"  ✅ Auto-logged {ticker} buy at ${buy_price:.2f}")


def check_exits():
    """Check all open trades and auto-close any that hit stop/target/time stop."""
    # Get all open trades (have buy price, no exit price)
    res = supabase.table("trades") \
        .select("*") \
        .is_("Exit Price", "null") \
        .not_.is_("Buy Price", "null") \
        .execute()

    if not res.data:
        print("No open trades to check")
        return

    alerts = []
    status_data = []

    for trade in res.data:
        ticker = trade["Robinhood"]
        buy_price = float(trade["Buy Price"])
        signal_date = pd.to_datetime(trade["Signal Date"]).date()
        trade_id = trade["Trade ID"]

        try:
            df = yf.download(ticker, period="3mo", interval="1d",
                             auto_adjust=False, progress=False)

            if df is None or df.empty:
                print(f"  ⚠️ {ticker}: no data")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            latest_close = float(df["Close"].iloc[-1])
            latest_date = df.index[-1].strftime("%Y-%m-%d")

            exits = exit_rules.calculate_exits(buy_price)
            stop = exits["stop_loss"]
            target = exits["profit_target"]
            days_held = get_trading_days_held(signal_date)
            pnl_pct = ((latest_close - buy_price) / buy_price) * 100

            # Determine exit reason
            exit_reason = None
            if latest_close <= stop:
                exit_reason = "Stop Loss"
            elif latest_close >= target:
                exit_reason = "Target Hit"
            elif days_held >= 10:
                exit_reason = "Time Stop"

            if exit_reason:
                win_loss = latest_close - buy_price

                # Write exit to Supabase
                supabase.table("trades").update({
                    "Exit Price": latest_close,
                    "Exit Date": latest_date,
                    "Exit Reason": exit_reason,
                    "Win/Loss": round(win_loss, 4),
                    "Days Held": days_held,
                }).eq("Trade ID", trade_id).execute()

                emoji = "🛑" if exit_reason == "Stop Loss" else "🎯" if exit_reason == "Target Hit" else "⏱️"
                alerts.append(
                    f"{emoji} **{ticker} — {exit_reason}**\n"
                    f"   Entry: ${buy_price:.2f} | Exit: ${latest_close:.2f} "
                    f"({pnl_pct:+.1f}%) | Day {days_held}/10"
                )
                print(f"  ✅ Closed {ticker} — {exit_reason} at ${latest_close:.2f}")

            else:
                distance_to_target = ((target - latest_close) / latest_close) * 100
                status_data.append({
                    "ticker": ticker,
                    "pnl_pct": pnl_pct,
                    "days_held": days_held,
                    "distance_to_target": distance_to_target,
                })
                print(f"  ✓ {ticker}: ${latest_close:.2f} | {pnl_pct:+.1f}% | Day {days_held}/10")

        except Exception as e:
            print(f"  ❌ {ticker}: {e}")

    # Build Discord message
    if alerts:
        msg = "🚨 **SwingTrade Alerts**\n\n" + "\n\n".join(alerts)
    elif status_data:
        status_data.sort(key=lambda x: x["pnl_pct"], reverse=True)
        avg_pnl = sum(d["pnl_pct"] for d in status_data) / len(status_data)
        lines = [
            f"{d['ticker']}: {d['pnl_pct']:+.1f}% (Day {d['days_held']}/10)"
            + (" 🎯" if d["distance_to_target"] < 1.0 else "")
            for d in status_data
        ]
        msg = f"✅ **All positions healthy — avg: {avg_pnl:+.1f}%**\n\n" + "\n".join(lines)
    else:
        msg = "✅ **No open positions**"

    send_discord_alert(msg)


def main():
    print(f"=== SwingTrade Alerts — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    print("--- Auto-logging new buys ---")
    auto_log_buys()

    print("\n--- Checking exits ---")
    check_exits()


if __name__ == "__main__":
    main()