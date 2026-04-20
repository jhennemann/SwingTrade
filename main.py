from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe
from src.setup_rules import PullbackUptrendSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, date

from src.ranking import rank_signals
from src.market_calendar import market_is_open

import os
from supabase import create_client


# ── Constants ──────────────────────────────────────────────────────────────────
STOP_PCT    = 0.98   # 2% below entry
TARGET_PCT  = 1.07   # 7% above entry
MAX_DAYS    = 10     # max market days to hold

# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

def send_signal_alert(today: pd.DataFrame, run_date: date, market_ok: bool, spy_close: float, spy_sma200: float):
    """Send daily scan summary to Discord."""
    if not DISCORD_WEBHOOK:
        print("No DISCORD_WEBHOOK_URL set — skipping signal alert")
        return

    if market_ok:
        market_line = f"SPY ✅ ${spy_close:.2f} (SMA200: ${spy_sma200:.2f})"
    else:
        market_line = f"SPY 🚫 ${spy_close:.2f} below SMA200 ${spy_sma200:.2f} — no trades"

    lines = [
        f"📊 **SwingTrade Scan — {run_date.isoformat()}**",
        market_line,
        "",
    ]

    if not today.empty:
        lines.append(f"**{len(today)} signal{'s' if len(today) != 1 else ''} today:**")
        for _, row in today.iterrows():
            rank = int(row["rank"]) if "rank" in row and pd.notna(row["rank"]) else "—"
            ticker = row["ticker"]
            rs = f"{row['relative_strength']:.1f}" if "relative_strength" in row and pd.notna(row["relative_strength"]) else "—"
            lines.append(f"#{rank}  {ticker}  |  RS: {rs}  |  Buy tomorrow's open")
    else:
        lines.append("No signals today.")

    message = "\n".join(lines)

    chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
    try:
        for chunk in chunks:
            response = requests.post(
                DISCORD_WEBHOOK,
                json={"content": chunk},
                timeout=10
            )
            response.raise_for_status()
        print("✅ Signal alert sent to Discord")
    except Exception as e:
        print(f"❌ Failed to send signal alert: {e}")


# ── Exit logic ─────────────────────────────────────────────────────────────────

def check_exits(supabase):
    """
    Fetch all open signals, check each for stop/target/time exit,
    and update Supabase rows with exit data when triggered.
    """
    response = supabase.table("signals").select("*").eq("status", "open").execute()
    open_signals = response.data

    if not open_signals:
        print("No open signals to check for exits.")
        return

    print(f"\n=== CHECKING EXITS FOR {len(open_signals)} OPEN SIGNALS ===")

    for signal in open_signals:
        ticker     = signal["ticker"]
        buy_price  = signal["buy_price"]
        last_date  = signal["last_date"]   # signal date — entry was next day open

        if not buy_price or not last_date:
            print(f"  {ticker}: missing buy_price or last_date, skipping")
            continue

        stop_price   = round(buy_price * STOP_PCT, 4)
        target_price = round(buy_price * TARGET_PCT, 4)

        # Download price history from signal date to today
        try:
            df = yf.download(
                ticker,
                start=last_date,
                end=date.today().isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False
            )
        except Exception as e:
            print(f"  {ticker}: download failed — {e}")
            continue

        if df is None or df.empty:
            print(f"  {ticker}: no price data returned")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Skip the signal date row itself — entry is next day open
        # so we start checking from the day after the signal
        df = df.iloc[1:].copy()

        if df.empty:
            print(f"  {ticker}: no post-entry price data yet")
            continue

        exit_price  = None
        exit_date   = None
        exit_reason = None
        days_held   = None

        for i, (idx, row) in enumerate(df.iterrows(), start=1):
            day_open  = float(row["Open"])
            day_high  = float(row["High"])
            day_low   = float(row["Low"])
            day_close = float(row["Close"])
            day_date  = idx.date() if hasattr(idx, 'date') else idx

            # On day 1, entry was at next-day open — use open as reference
            entry = day_open if i == 1 else None

            # Check stop (low breached stop price)
            hit_stop   = day_low <= stop_price
            # Check target (high reached target price)
            hit_target = day_high >= target_price
            # Check time exit (max days reached)
            hit_time   = i >= MAX_DAYS

            if hit_stop and hit_target:
                # Both hit same day — conservative: stop wins
                exit_price  = stop_price
                exit_date   = day_date
                exit_reason = "stop"
                days_held   = i
                break
            elif hit_stop:
                exit_price  = stop_price
                exit_date   = day_date
                exit_reason = "stop"
                days_held   = i
                break
            elif hit_target:
                exit_price  = target_price
                exit_date   = day_date
                exit_reason = "target"
                days_held   = i
                break
            elif hit_time:
                exit_price  = day_close
                exit_date   = day_date
                exit_reason = "time"
                days_held   = i
                break

        if exit_price is not None:
            win_loss = round((exit_price - buy_price) / buy_price, 4)

            update = {
                "status":      "closed",
                "exit_price":  exit_price,
                "exit_date":   exit_date.isoformat(),
                "exit_reason": exit_reason,
                "win_loss":    win_loss,
                "days_held":   days_held,
            }

            try:
                supabase.table("signals").update(update).eq("id", signal["id"]).execute()
                print(f"  ✓ {ticker}: {exit_reason} exit on {exit_date} | P&L: {win_loss*100:.2f}% | days: {days_held}")
            except Exception as e:
                print(f"  ❌ {ticker}: failed to update Supabase — {e}")
        else:
            print(f"  {ticker}: still open ({len(df)} days in trade)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not market_is_open():
        print("Market is closed today. Skipping scan.")
        return

    # Load universes
    print("Loading stock universes...")
    sp500 = SP500UniverseStockAnalysis()
    print(f"✓ S&P 500: {len(sp500.tickers)} stocks")

    nasdaq100 = Nasdaq100Universe()
    print(f"✓ NASDAQ 100: {len(nasdaq100.tickers)} stocks")

    all_tickers = list(set(sp500.tickers + nasdaq100.tickers))
    overlap = len(sp500.tickers) + len(nasdaq100.tickers) - len(all_tickers)
    print(f"✓ Combined universe: {len(all_tickers)} stocks ({overlap} overlap)")
    print()

    setup = PullbackUptrendSetup(
        pullback_pct=0.02,
        use_volume=True
    )

    scanner = SetupScanner(
        setup=setup,
        lookback="2y",
        require_market_ok=True
    )

    market_ok, spy_date, spy_close, spy_sma200 = scanner.market_ok()

    results = scanner.scan(all_tickers)

    today = results[results["has_signal_today"]] if not results.empty else pd.DataFrame()

    if not today.empty:
        today = rank_signals(today)
        results = results.set_index('ticker')
        today_indexed = today.set_index('ticker')
        results.update(today_indexed)
        results = results.reset_index()

    print("\n=== SIGNALS TODAY ===")
    if not today.empty:
        display_cols = [c for c in ["rank", "ticker", "relative_strength", "last_date"] if c in today.columns]
        print(today[display_cols].to_string(index=False))
    else:
        print("No signals today.")

    # Determine run date
    run_date = date.today() if today.empty else pd.to_datetime(today["last_date"].iloc[0]).date()

    # Chart generator
    chart_gen = ChartGenerator(base_dir="data/charts")
    chart_paths = []

    for _, row in today.iterrows():
        ticker = row["ticker"]
        signal_date = pd.to_datetime(row["most_recent_signal_date"])

        df = yf.download(
            ticker,
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty:
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = setup.prepare(df)

        chart_path = chart_gen.save_chart(
            df=df,
            ticker=ticker,
            signal_date=signal_date,
            run_date=run_date,
            filename="pullback_setup.png"
        )

        chart_paths.append(chart_path)
        print(f"Saved chart: {chart_path}")

    # Export PDF gallery
    if chart_paths:
        pdf_out = (
            f"data/charts/"
            f"{run_date.year:04d}/"
            f"{run_date.month:02d}/"
            f"{run_date.isoformat()}/"
            f"gallery_{run_date.isoformat()}.pdf"
        )
        exporter = PDFGalleryExporter(cols=2, rows=2)
        pdf_path = exporter.export(
            image_paths=chart_paths,
            output_pdf_path=pdf_out,
            title="SwingTrade Setup Gallery - S&P 500 + NASDAQ 100",
            subtitle=(
                f"Signal date: {run_date.isoformat()} | "
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                f"Universe: {len(all_tickers)} stocks"
            ),
        )
        print(f"\nSaved PDF gallery: {pdf_path}")
    else:
        print("\nNo charts generated; skipping PDF export.")

    # Save scan results CSV
    csv_path = (
        f"data/charts/"
        f"{run_date.year:04d}/"
        f"{run_date.month:02d}/"
        f"{run_date.isoformat()}/"
        f"scan_results_{run_date.isoformat()}.csv"
    )

    if not today.empty:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        today.to_csv(csv_path, index=False)
        print(f"\nSaved signals with RS: {csv_path}")
    else:
        print(f"\nNo signals today - skipping CSV save")

    # ── Supabase ───────────────────────────────────────────────────────────────
    supabase_url     = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if supabase_url and supabase_service_key:
        try:
            supabase = create_client(supabase_url, supabase_service_key)

            # 1. Check exits for all currently open signals
            check_exits(supabase)

            # 2. Push today's new signals
            if not today.empty:
                supabase.table("signals").delete().eq("last_date", run_date.isoformat()).execute()

                records = today.to_dict(orient="records")
                for record in records:
                    for k, v in record.items():
                        if isinstance(v, float) and np.isnan(v):
                            record[k] = None
                        elif hasattr(v, 'isoformat'):
                            record[k] = v.isoformat()
                    # New signals start as open with no exit data
                    record["status"] = "open"

                supabase.table("signals").insert(records).execute()
                print(f"\n✓ Pushed {len(records)} new signals to Supabase")
            else:
                print("\nNo new signals to push to Supabase")

        except Exception as e:
            print(f"❌ Supabase error: {e}")
    else:
        print("Supabase credentials not found, skipping")

    # Send Discord signal alert
    send_signal_alert(
        today=today,
        run_date=run_date,
        market_ok=market_ok,
        spy_close=spy_close or 0.0,
        spy_sma200=spy_sma200 or 0.0,
    )


if __name__ == "__main__":
    main()