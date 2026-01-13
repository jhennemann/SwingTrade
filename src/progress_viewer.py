from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from io import BytesIO

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

from src.pdf_pair_exporter import PDFPairExporter


def parse_date(d: str) -> str:
    """
    Accepts:
      - YYYY-MM-DD
      - M/D or MM/DD (assumes most recent past date)
    Returns YYYY-MM-DD
    """
    today = date.today()

    if "-" in d:
        datetime.strptime(d, "%Y-%m-%d")
        return d

    month, day = map(int, d.split("/"))
    candidate = date(today.year, month, day)

    if candidate > today:
        candidate = date(today.year - 1, month, day)

    return candidate.isoformat()


def normalize_to_100(series: pd.Series) -> pd.Series:
    series = series.dropna()
    if series.empty:
        return series
    return (series / series.iloc[0]) * 100


def fig_to_png_bytes(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


@dataclass
class ProgressViewer:
    out_dir: str = "data/progress"

    def _download(self, ticker: str, start_date: str) -> pd.DataFrame:
        df = yf.download(
            ticker,
            start=start_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        expected = {"Open", "High", "Low", "Close", "Volume"}
        if not expected.issubset(df.columns):
            return pd.DataFrame()

        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
        return df

    def _run_dir(self, run_date: date, ticker: str) -> str:
        safe_ticker = ticker.replace("/", "-")
        return os.path.join(
            self.out_dir,
            f"{run_date.year:04d}",
            f"{run_date.month:02d}",
            f"{run_date.day:02d}",
            safe_ticker,
        )

    def save_progress_report(
        self,
        ticker: str,
        start_date: str,
        benchmark: str = "^GSPC",
        technical_lookback_days: int = 90,
        indicator_history_days: int = 365,
        run_date: date | None = None,
    ) -> dict[str, str]:
        """
        Saves ONLY:
          - report.pdf (technical+volume above performance)
          - meta.json  (summary metrics for the run)

        Folder structure:
          data/progress/YYYY/MM/DD/TICKER/

        Returns paths: {"pdf": ..., "json": ...}
        """
        run_date = run_date or date.today()
        run_dir = self._run_dir(run_date, ticker)
        os.makedirs(run_dir, exist_ok=True)

        safe_ticker = ticker.replace("/", "-")

        # -------------------------
        # Performance: start_date -> today
        # -------------------------
        stock_perf = self._download(ticker, start_date)
        if stock_perf.empty:
            raise ValueError(f"No data returned for {ticker} starting {start_date}")

        bench_perf = self._download(benchmark, start_date)
        if bench_perf.empty:
            raise ValueError(f"No benchmark data returned for {benchmark} starting {start_date}")

        perf = pd.concat([stock_perf["Close"], bench_perf["Close"]], axis=1, join="inner").dropna()
        perf.columns = [ticker, benchmark]
        if perf.empty:
            raise ValueError("No overlapping dates between stock and benchmark for performance window.")

        stock_change = (perf[ticker].iloc[-1] / perf[ticker].iloc[0] - 1) * 100
        bench_change = (perf[benchmark].iloc[-1] / perf[benchmark].iloc[0] - 1) * 100

        stock_norm = normalize_to_100(perf[ticker])
        bench_norm = normalize_to_100(perf[benchmark])

        # Build performance figure (in memory)
        fig1 = plt.figure(figsize=(12, 6))
        plt.plot(stock_norm.index, stock_norm, label=f"{safe_ticker} (norm)")
        plt.plot(bench_norm.index, bench_norm, label=f"{benchmark} (norm)")
        plt.axvline(pd.to_datetime(start_date), linestyle="--", linewidth=1, label="Start")
        plt.title(
            f"{safe_ticker} vs {benchmark} since {start_date}\n"
            f"{safe_ticker}: {stock_change:+.2f}%   |   {benchmark}: {bench_change:+.2f}%"
        )
        plt.xlabel("Date")
        plt.ylabel("Normalized performance (start = 100)")
        plt.legend()
        plt.tight_layout()
        perf_png = fig_to_png_bytes(fig1)

        # -------------------------
        # Technical: price + SMA + volume (stacked)
        # -------------------------
        today = run_date  # use run_date as the "today" anchor for reproducibility
        indicator_start = (today - timedelta(days=indicator_history_days)).isoformat()

        stock_tech = self._download(ticker, indicator_start)
        if stock_tech.empty:
            raise ValueError(f"No data returned for {ticker} starting {indicator_start}")

        stock_tech_ind = self._add_indicators(stock_tech)

        plot_start = today - timedelta(days=technical_lookback_days)
        stock_tech_plot = stock_tech_ind[stock_tech_ind.index >= pd.to_datetime(plot_start)]
        if stock_tech_plot.empty:
            raise ValueError(
                f"Technical plot window is empty for {ticker}. Plot start was {plot_start.isoformat()}."
            )

        # Create a 2-row figure: price on top, volume on bottom
        fig2, (ax_price, ax_vol) = plt.subplots(
            2,
            1,
            figsize=(12, 7),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )

        # ---- Price + SMAs ----
        ax_price.plot(stock_tech_plot.index, stock_tech_plot["Close"], label="Close", linewidth=1.5)
        ax_price.plot(stock_tech_plot.index, stock_tech_plot["SMA20"], label="SMA20", linestyle="--")
        ax_price.plot(stock_tech_plot.index, stock_tech_plot["SMA50"], label="SMA50", linestyle="--")

        start_dt = pd.to_datetime(start_date)
        ax_price.axvline(start_dt, color="red", linestyle=":", linewidth=1.5, label="Signal date")

        ax_price.set_title(f"{safe_ticker} technical view (last {technical_lookback_days} days)")
        ax_price.legend(loc="upper left")
        ax_price.grid(True)

        # ---- Volume ----
        ax_vol.bar(stock_tech_plot.index, stock_tech_plot["Volume"], width=1.0, label="Volume")
        ax_vol.plot(stock_tech_plot.index, stock_tech_plot["VOL_SMA20"], label="VOL_SMA20", linewidth=1.2)

        ax_vol.axvline(start_dt, color="red", linestyle=":", linewidth=1.0)
        ax_vol.set_ylabel("Volume")
        ax_vol.legend(loc="upper left")
        ax_vol.grid(True)

        plt.tight_layout()
        tech_png = fig_to_png_bytes(fig2)

        # -------------------------
        # Write PDF (only artifact)
        # -------------------------
        pdf_path = os.path.join(run_dir, "report.pdf")
        pair = PDFPairExporter()
        pair.export(
            perf_img=perf_png,
            tech_img=tech_png,
            output_pdf_path=pdf_path,
            title=f"{safe_ticker} Progress Report",
            subtitle=(
                f"Run: {run_date.isoformat()} | Signal: {start_date} | Benchmark: {benchmark} | "
                f"{safe_ticker} {stock_change:+.2f}% | {benchmark} {bench_change:+.2f}%"
            ),
        )

        # -------------------------
        # Write JSON metadata (only other artifact)
        # -------------------------
        meta = {
            "ticker": safe_ticker,
            "run_date": run_date.isoformat(),
            "signal_date": start_date,
            "benchmark": benchmark,
            "technical_lookback_days": technical_lookback_days,
            "indicator_history_days": indicator_history_days,
            "stock_change_pct": float(round(stock_change, 6)),
            "benchmark_change_pct": float(round(bench_change, 6)),
            "relative_outperformance_pct": float(round(stock_change - bench_change, 6)),
            "perf_start_close": float(perf[ticker].iloc[0]),
            "perf_end_close": float(perf[ticker].iloc[-1]),
            "bench_start_close": float(perf[benchmark].iloc[0]),
            "bench_end_close": float(perf[benchmark].iloc[-1]),
        }

        json_path = os.path.join(run_dir, "meta.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        print(f"{safe_ticker} change since {start_date}: {stock_change:+.2f}%")
        print(f"{benchmark} change since {start_date}: {bench_change:+.2f}%")
        print(f"Saved PDF:  {pdf_path}")
        print(f"Saved JSON: {json_path}")

        return {"pdf": pdf_path, "json": json_path}


def main():
    if len(sys.argv) != 3:
        print("Usage: python -m src.progress_viewer <TICKER> <DATE>")
        print("Examples:")
        print("  python -m src.progress_viewer PRU 1/2")
        print("  python -m src.progress_viewer PRU 2026-01-02")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    start_date = parse_date(sys.argv[2])

    viewer = ProgressViewer()
    paths = viewer.save_progress_report(ticker=ticker, start_date=start_date)

    print(f"Saved report PDF: {paths['pdf']}")
    print(f"Saved meta JSON:  {paths['json']}")


if __name__ == "__main__":
    main()
