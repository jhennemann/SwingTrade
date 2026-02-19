from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe
from src.setup_rules import PullbackUptrendSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
from datetime import datetime, date

from src.ranking import rank_signals
from src.market_calendar import market_is_open



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

    results = scanner.scan(all_tickers)

    today = results[results["has_signal_today"]]

    if not today.empty:
        today = rank_signals(today)
        # Merge ranked data back into results
        results = results.set_index('ticker')
        today_indexed = today.set_index('ticker')
        results.update(today_indexed)
        results = results.reset_index()

    print("\n=== SIGNALS TODAY ===")

    if not today.empty:
        # Show the columns that exist
        display_cols = []
        for col in ["rank", "ticker", "relative_strength", "last_date"]:
            if col in today.columns:
                display_cols.append(col)
        print(today[display_cols].to_string(index=False))
    else:
        print("No signals today.")

    # -------------------------------------------------
    # Determine the RUN DATE for this scan
    # -------------------------------------------------
    if today.empty:
        print("\nNo signals today.")
        run_date = date.today()
    else:
        # last_date is already the scan date (Timestamp or string)
        run_date = pd.to_datetime(today["last_date"].iloc[0]).date()

    # -------------------------------------------------
    # Chart generator (ROOT ONLY — no date here)
    # -------------------------------------------------
    chart_gen = ChartGenerator(base_dir="data/charts")
    chart_paths = []

    # -------------------------------------------------
    # Generate charts per ticker
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Export PDF gallery (optional)
    # -------------------------------------------------
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

    # -------------------------------------------------
    # Save scan results
    # -------------------------------------------------
    csv_path = (
    f"data/charts/"
    f"{run_date.year:04d}/"
    f"{run_date.month:02d}/"
    f"{run_date.isoformat()}/"
    f"scan_results_{run_date.isoformat()}.csv"
    )
    results.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")
    print("\nSaved: scan_results.csv")


if __name__ == "__main__":
    main()