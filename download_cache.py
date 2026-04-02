"""
download_cache.py

Downloads OHLCV price data for the full S&P 500 + NASDAQ 100 universe
and saves each ticker as a CSV file in the cache/ folder.

Run this once (or whenever you want to refresh prices):
    python download_cache.py

After this, backtest_2025.py reads from cache/ instead of hitting yfinance,
so backtests start in seconds regardless of config changes.

Cache folder structure:
    cache/
        AAPL.csv
        MSFT.csv
        SPY.csv
        ...
"""

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe

# ── Config ─────────────────────────────────────────────────────────────────────
DOWNLOAD_START          = "2024-01-01"  # Start early so SMAs are warm by Jan 2025
DOWNLOAD_END            = "2026-01-01"
CACHE_DIR               = Path("cache")
SLEEP_BETWEEN_DOWNLOADS = 0.1          # Light throttle to avoid rate limiting


# ── Helpers ────────────────────────────────────────────────────────────────────
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns, sort by date, cast to float."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = df[col].astype(float)
    return df


def download_ticker(ticker: str) -> pd.DataFrame | None:
    """Download one ticker from yfinance and return cleaned DataFrame."""
    df = yf.download(
        ticker,
        start=DOWNLOAD_START,
        end=DOWNLOAD_END,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )
    if df is None or df.empty:
        return None
    return clean_df(df)


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SwingTrade Cache Downloader")
    print("=" * 60 + "\n")

    # Create cache directory
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"Cache directory: {CACHE_DIR.resolve()}\n")

    # Load universe
    print("Loading universe...")
    sp500   = SP500UniverseStockAnalysis().tickers
    nasdaq  = Nasdaq100Universe().tickers
    tickers = sorted(set(sp500 + nasdaq))
    print(f"  S&P 500: {len(sp500)} | NASDAQ 100: {len(nasdaq)} | Combined: {len(tickers)}\n")

    # Always include SPY for market filter + RS calculation
    if "SPY" not in tickers:
        tickers = ["SPY"] + tickers

    # Check which tickers already have a cache file — skip them
    existing  = {f.stem for f in CACHE_DIR.glob("*.csv")}
    to_download = [t for t in tickers if t not in existing]

    if existing:
        print(f"Already cached: {len(existing)} tickers — skipping")
    print(f"To download: {len(to_download)} tickers\n")

    if not to_download:
        print("Cache is up to date. Nothing to download.")
        print("To force a full refresh, delete the cache/ folder and re-run.")
        return

    # Download and save
    ok     = 0
    failed = []

    for i, ticker in enumerate(to_download, 1):
        try:
            df = download_ticker(ticker)

            if df is None:
                failed.append(ticker)
            else:
                df.to_csv(CACHE_DIR / f"{ticker}.csv")
                ok += 1

            if i % 50 == 0 or i == len(to_download):
                print(f"  [{i}/{len(to_download)}] done — {ok} saved, {len(failed)} failed")

            time.sleep(SLEEP_BETWEEN_DOWNLOADS)

        except Exception as e:
            failed.append(ticker)
            print(f"  ⚠ {ticker}: {e}")

    print(f"\n✓ Cache complete: {ok} tickers saved to {CACHE_DIR}/")

    if failed:
        print(f"  Failed ({len(failed)}): {failed}")
        print("  Re-run the script to retry failed tickers — existing files are skipped automatically.")


if __name__ == "__main__":
    main()