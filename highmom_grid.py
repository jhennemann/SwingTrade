"""
grid_search_highmom.py

Grid search over stop loss and profit target combinations for the
52-week high momentum strategy. Tests all combinations and outputs
a summary table ranked by avg return at RS > 50, volume > 1.75x.

Usage:
    python grid_search_highmom.py

Outputs:
    grid_search_results.csv
"""

from datetime import date
from pathlib import Path
from itertools import product

import pandas as pd

from src.setup_rules import HighMomentumSetup


CACHE_DIR = Path("cache")
SCAN_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
MAX_HOLD_DAYS = 10
RS_FILTER = 50
VOLUME_FILTER = 1.75

STOP_LOSSES = [0.01, 0.02, 0.03, 0.04]
PROFIT_TARGETS = [0.05, 0.07, 0.10, 0.15]

OUTPUT = Path("grid_search_results.csv")


def load_universe_from_web_or_cache() -> list[str]:
    try:
        from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe
        sp500 = SP500UniverseStockAnalysis().tickers
        nasdaq = Nasdaq100Universe().tickers
        tickers = sorted(set(sp500 + nasdaq))
        print(f"Universe loaded from web: {len(tickers)} tickers")
        return tickers
    except Exception as exc:
        print(f"Universe download failed, using cached tickers: {exc}")
        tickers = sorted(path.stem for path in CACHE_DIR.glob("*.csv") if path.stem != "SPY")
        print(f"Cached universe: {len(tickers)} tickers")
        return tickers


def calculate_rs_from_cache(ticker: str, signal_date, cache: dict, lookback_days: int = 60) -> float:
    try:
        stock = cache.get(ticker)
        spy = cache.get("SPY")
        if stock is None or spy is None:
            return 0.0
        stock = stock[stock.index.date <= signal_date]
        spy = spy[spy.index.date <= signal_date]
        if len(stock) < lookback_days or len(spy) < lookback_days:
            return 0.0
        stock_return = (stock["Close"].iloc[-1] / stock["Close"].iloc[-lookback_days]) - 1
        spy_return = (spy["Close"].iloc[-1] / spy["Close"].iloc[-lookback_days]) - 1
        return float((stock_return - spy_return) * 100)
    except:
        return 0.0


def load_price_cache(tickers: list[str]) -> dict[str, pd.DataFrame]:
    if not CACHE_DIR.exists():
        raise FileNotFoundError("cache/ not found. Run python download_cache.py first.")
    cache = {}
    for ticker in sorted(set(tickers + ["SPY"])):
        path = CACHE_DIR / f"{ticker}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        needed = ["Open", "High", "Low", "Close", "Volume"]
        if all(col in df.columns for col in needed):
            cache[ticker] = df[needed].dropna().astype(float)
    print(f"Loaded cached data for {len(cache)} tickers")
    return cache


def build_market_filter(cache: dict, scan_year: int) -> set[date] | None:
    spy = cache.get("SPY")
    if spy is None or spy.empty:
        return None
    spy = spy.copy()
    spy["SMA200"] = spy["Close"].rolling(200).mean()
    return set(
        idx.date()
        for idx, row in spy.iterrows()
        if idx.year == scan_year and row["Close"] > row["SMA200"]
    )


def detect_signals(cache, tickers, setup) -> list[dict]:
    """Detect all signals across all years, calculate RS once."""
    all_signals = []
    for scan_year in SCAN_YEARS:
        valid_market_dates = build_market_filter(cache, scan_year)
        for ticker in tickers:
            df = cache.get(ticker)
            if df is None or len(df) < 252:
                continue
            try:
                prepared = setup.prepare(df)
                applied = setup.apply(prepared)
                signal_rows = applied[
                    applied["signal"] &
                    (applied.index.year == scan_year)
                ]
                for idx, row in signal_rows.iterrows():
                    signal_date = idx.date()
                    if valid_market_dates is not None and signal_date not in valid_market_dates:
                        continue
                    all_signals.append({
                        "ticker": ticker,
                        "signal_date": signal_date,
                        "entry_price": float(row["Close"]),
                        "high_52w": float(row["high_52w"]),
                        "volume_ratio": float(row["volume_ratio"]),
                        "year": scan_year,
                        "relative_strength": calculate_rs_from_cache(ticker, signal_date, cache),
                    })
            except:
                continue
    return all_signals


def simulate_all_trades(signals: list[dict], cache: dict, stop_pct: float, target_pct: float) -> pd.DataFrame:
    trades = []
    for signal in signals:
        ticker = signal["ticker"]
        df = cache.get(ticker)
        if df is None:
            continue

        signal_date = signal["signal_date"]
        future = df[df.index.date > signal_date].head(MAX_HOLD_DAYS + 1)
        if future.empty or len(future) < 2:
            continue

        entry_price = float(future.iloc[0]["Open"])
        if entry_price <= 0:
            continue

        stop_price = entry_price * (1 - stop_pct)
        target_price = entry_price * (1 + target_pct)
        trading_days = future.iloc[1:]

        exit_price = None
        exit_reason = None

        for i, (idx, row) in enumerate(trading_days.iterrows(), 1):
            low = float(row["Low"])
            high = float(row["High"])
            close = float(row["Close"])

            if low <= stop_price and high >= target_price:
                exit_price = stop_price
                exit_reason = "Stop Loss"
                break
            if low <= stop_price:
                exit_price = stop_price
                exit_reason = "Stop Loss"
                break
            if high >= target_price:
                exit_price = target_price
                exit_reason = "Profit Target"
                break
            if i >= MAX_HOLD_DAYS:
                exit_price = close
                exit_reason = "Time Exit"
                break

        if exit_price is None:
            continue

        pnl = (exit_price - entry_price) / entry_price
        trades.append({
            "ticker": ticker,
            "signal_date": signal_date,
            "year": signal["year"],
            "relative_strength": signal["relative_strength"],
            "volume_ratio": signal["volume_ratio"],
            "pnl": pnl,
            "win": pnl > 0,
            "exit_reason": exit_reason,
        })

    return pd.DataFrame(trades)


def main():
    print("=" * 60)
    print("  High Momentum Grid Search")
    print("=" * 60 + "\n")

    tickers = load_universe_from_web_or_cache()
    cache = load_price_cache(tickers)

    setup = HighMomentumSetup(
        near_high_pct=0.02,
        volume_ratio_min=VOLUME_FILTER,
        lookback_days=252,
    )

    print("\nDetecting signals once for all years...")
    all_signals = detect_signals(cache, tickers, setup)
    print(f"Total raw signals: {len(all_signals)}")

    # Apply RS and volume filters
    filtered = [
        s for s in all_signals
        if s["relative_strength"] > RS_FILTER
        and s["volume_ratio"] > VOLUME_FILTER
    ]
    print(f"Filtered signals (RS>{RS_FILTER}, Vol>{VOLUME_FILTER}x): {len(filtered)}\n")

    results = []
    combinations = list(product(STOP_LOSSES, PROFIT_TARGETS))
    print(f"Testing {len(combinations)} combinations...\n")

    for stop_pct, target_pct in combinations:
        trades_df = simulate_all_trades(filtered, cache, stop_pct, target_pct)
        if trades_df.empty:
            continue

        winners = trades_df[trades_df["pnl"] > 0]
        losers = trades_df[trades_df["pnl"] <= 0]

        results.append({
            "stop_pct": f"{stop_pct*100:.0f}%",
            "target_pct": f"{target_pct*100:.0f}%",
            "total_trades": len(trades_df),
            "win_rate": round(trades_df["win"].mean() * 100, 2),
            "avg_return": round(trades_df["pnl"].mean() * 100, 2),
            "avg_winner": round(winners["pnl"].mean() * 100, 2) if not winners.empty else None,
            "avg_loser": round(losers["pnl"].mean() * 100, 2) if not losers.empty else None,
            "risk_reward": round(target_pct / stop_pct, 2),
        })

        print(f"Stop {stop_pct*100:.0f}% / Target {target_pct*100:.0f}%: "
              f"{len(trades_df)} trades, "
              f"{trades_df['win'].mean()*100:.1f}% WR, "
              f"{trades_df['pnl'].mean()*100:.2f}% avg return")

    results_df = pd.DataFrame(results).sort_values("avg_return", ascending=False)
    results_df.to_csv(OUTPUT, index=False)

    print(f"\n{'='*60}")
    print("  Results ranked by avg return")
    print(f"{'='*60}")
    print(results_df.to_string(index=False))
    print(f"\nSaved: {OUTPUT}")


if __name__ == "__main__":
    main()