from src.universe import SP500UniverseStockAnalysis
from src.setup_rules import PullbackUptrendSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
from datetime import datetime


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

    # ---- generate charts ----
    signal_day = today["last_date"].iloc[0] if not today.empty else "unknown-date"
    chart_output_dir = f"data/charts/{signal_day}"

    chart_gen = ChartGenerator(output_dir=chart_output_dir) 
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
            signal_date=signal_date
        )

        chart_paths.append(chart_path)
        print(f"Saved chart: {chart_path}")

    # ---- export PDF gallery ----
    if chart_paths:
        # Use the signal day shown in your table (last_date is already string like 2026-01-02)
        signal_day = today["last_date"].iloc[0] if not today.empty else "unknown-date"
        pdf_out = f"{chart_output_dir}/gallery_{signal_day}.pdf"

        exporter = PDFGalleryExporter(cols=2, rows=2)
        pdf_path = exporter.export(
            image_paths=chart_paths,
            output_pdf_path=pdf_out,
            title="SwingTrade Setup Gallery",
            subtitle=f"Signal date: {signal_day} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )

        print(f"\nSaved PDF gallery: {pdf_path}")
    else:
        print("\nNo charts generated; skipping PDF export.")

    results.to_csv("scan_results.csv", index=False)
    print("\nSaved: scan_results.csv")


if __name__ == "__main__":
    main()
