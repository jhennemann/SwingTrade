from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe
from src.setup_rules import PullbackUptrendSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, date

from src.ranking import rank_signals
from src.market_calendar import market_is_open

import os
from supabase import create_client


# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

def send_signal_alert(today: pd.DataFrame, run_date: date, market_ok: bool, spy_close: float, spy_sma200: float):
    """Send daily scan summary to Discord."""
    if not DISCORD_WEBHOOK:
        print("No DISCORD_WEBHOOK_URL set — skipping signal alert")
        return

    # Market status line
    if market_ok:
        market_line = f"SPY ✅ ${spy_close:.2f} (SMA200: ${spy_sma200:.2f})"
    else:
        market_line = f"SPY 🚫 ${spy_close:.2f} below SMA200 ${spy_sma200:.2f} — no trades"

    # Header
    lines = [
        f"📊 **SwingTrade Scan — {run_date.isoformat()}**",
        market_line,
        "",
    ]

    # Signals
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

    # Send (chunked if needed)
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

    # Combine and deduplicate
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

    # Check market filter before full scan so we can pass status to alert
    market_ok, spy_date, spy_close, spy_sma200 = scanner.market_ok()

    results = scanner.scan(all_tickers)

    today = results[results["has_signal_today"]] if not results.empty else pd.DataFrame()

    if not today.empty:
        today = rank_signals(today)
        # Merge ranked data back into results
        results = results.set_index('ticker')
        today_indexed = today.set_index('ticker')
        results.update(today_indexed)
        results = results.reset_index()

    print("\n=== SIGNALS TODAY ===")

    if not today.empty:
        display_cols = []
        for col in ["rank", "ticker", "relative_strength", "last_date"]:
            if col in today.columns:
                display_cols.append(col)
        print(today[display_cols].to_string(index=False))
    else:
        print("No signals today.")

    # Determine run date
    if today.empty:
        run_date = date.today()
    else:
        run_date = pd.to_datetime(today["last_date"].iloc[0]).date()

    # Chart generator
    chart_gen = ChartGenerator(base_dir="data/charts")
    chart_paths = []

    # Generate charts per ticker
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

    # Push to Supabase
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY")

    if supabase_url and supabase_key:
        try:
            supabase = create_client(supabase_url, supabase_key)

            df_to_push = today if not today.empty else pd.DataFrame()

            if not df_to_push.empty:
                supabase.table("signals").delete().eq("last_date", run_date.isoformat()).execute()

                records = df_to_push.to_dict(orient="records")
                for record in records:
                    for k, v in record.items():
                        if pd.isna(v):
                            record[k] = None
                        elif hasattr(v, 'isoformat'):
                            record[k] = v.isoformat()

                supabase.table("signals").insert(records).execute()
                print(f"✓ Pushed {len(records)} signals to Supabase")
            else:
                print("No signals to push to Supabase")
        except Exception as e:
            print(f"❌ Failed to push to Supabase: {e}")
    else:
        print("Supabase credentials not found, skipping push")

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