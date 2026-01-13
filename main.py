from src.universe import SP500UniverseStockAnalysis
from src.setup_rules import PullbackUptrendSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
from datetime import datetime, date


def main():
    universe = SP500UniverseStockAnalysis()

    setup = PullbackUptrendSetup(
        pullback_pct=0.01,
        use_volume=True
    )

    scanner = SetupScanner(
        setup=setup,
        lookback="2y",
        require_market_ok=True
    )

    results = scanner.scan(universe.tickers)

    print("\n=== SIGNALS TODAY ===")
    today = results[results["has_signal_today"]]
    print(today.to_string(index=False))

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
            run_date=run_date,  # 🔑 ensures YYYY/MM/DD matches scan date
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
            title="SwingTrade Setup Gallery",
            subtitle=(
                f"Signal date: {run_date.isoformat()} | "
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            ),
        )

        print(f"\nSaved PDF gallery: {pdf_path}")
    else:
        print("\nNo charts generated; skipping PDF export.")

    # -------------------------------------------------
    # Save scan results
    # -------------------------------------------------
    results.to_csv("scan_results.csv", index=False)
    print("\nSaved: scan_results.csv")


if __name__ == "__main__":
    main()
