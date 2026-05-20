"""
breakout_scan.py

Daily breakout candidate scanner for the S&P 500 + Nasdaq 100 universe.
This lives beside the existing pullback scanner and does not change main.py.

Usage:
    python breakout_scan.py

Output:
    breakout_scan_results.csv
"""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from src.setup_rules import BreakoutSetup
from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe


OUTPUT_CSV = "breakout_scan_results.csv"


def load_universe() -> list[str]:
    sp500 = SP500UniverseStockAnalysis().tickers
    nasdaq = Nasdaq100Universe().tickers
    return sorted(set(sp500 + nasdaq))


def download_price_data(ticker: str, period: str = "2y") -> pd.DataFrame:
    df = yf.download(
        ticker,
        period=period,
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

    expected = ["Open", "High", "Low", "Close", "Volume"]
    if any(col not in df.columns for col in expected):
        return pd.DataFrame()
    return df[expected].dropna()


def has_earnings_soon(ticker: str, trading_days: int = 5) -> bool:
    """
    Best-effort yfinance earnings check.

    yfinance does not always return upcoming earnings dates, so missing or
    malformed data is treated as unknown rather than a hard exclusion.
    """
    try:
        stock = yf.Ticker(ticker)
        calendar = stock.calendar
        if calendar is None or len(calendar) == 0:
            return False

        earnings_date = None
        if isinstance(calendar, dict):
            earnings_date = calendar.get("Earnings Date")
        elif isinstance(calendar, pd.DataFrame):
            if "Earnings Date" in calendar.index:
                earnings_date = calendar.loc["Earnings Date"].iloc[0]
            elif "Earnings Date" in calendar.columns:
                earnings_date = calendar["Earnings Date"].iloc[0]

        if isinstance(earnings_date, (list, tuple)):
            earnings_date = earnings_date[0] if earnings_date else None
        if earnings_date is None or pd.isna(earnings_date):
            return False

        earnings_day = pd.to_datetime(earnings_date).date()
        today = date.today()
        calendar_days = trading_days + 3
        return today <= earnings_day <= today + timedelta(days=calendar_days)
    except Exception:
        return False


def main():
    print("=" * 60)
    print("  Breakout Strategy Scanner")
    print("=" * 60 + "\n")

    tickers = load_universe()
    print(f"Universe: {len(tickers)} tickers\n")

    setup = BreakoutSetup(
        min_base_days=15,
        max_base_days=30,
        max_range_pct=0.05,
        near_resistance_pct=0.03,
        volume_ratio_min=1.5,
        breakout_only=False,
    )

    rows = []
    for i, ticker in enumerate(tickers, 1):
        df = download_price_data(ticker)
        if df.empty or len(df) < 230:
            continue

        try:
            prepared = setup.prepare(df)
            signals = setup.apply(prepared)
            last = signals.iloc[-1]

            if bool(last["signal"]) and not has_earnings_soon(ticker):
                rows.append({
                    "ticker": ticker,
                    "last_date": signals.index[-1].date().isoformat(),
                    "current_price": round(float(last["Close"]), 2),
                    "resistance_level": round(float(last["resistance_level"]), 2),
                    "volume_ratio": round(float(last["volume_ratio"]), 2),
                    "consolidation_length": int(last["consolidation_length"]),
                    "base_low": round(float(last["base_low"]), 2),
                    "base_range_pct": round(float(last["base_range_pct"]) * 100, 2),
                    "breakout": bool(last["breakout"]),
                })
        except Exception as exc:
            print(f"  {ticker}: {exc}")

        if i % 100 == 0:
            print(f"Scanned {i}/{len(tickers)} tickers...")

    results = pd.DataFrame(rows)
    if not results.empty:
        results = results.sort_values(
            by=["breakout", "volume_ratio", "base_range_pct"],
            ascending=[False, False, True],
        ).reset_index(drop=True)

    results.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSignals: {len(results)}")
    print(f"Saved: {OUTPUT_CSV}")
    if not results.empty:
        print(results.to_string(index=False))


if __name__ == "__main__":
    main()
