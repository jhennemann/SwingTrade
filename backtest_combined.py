"""
backtest_combined.py

Combined pullback + breakout strategy backtest.
Runs both setups daily, ranks all signals by RS, takes the top 1 signal per day.
Breakout signals are preferred as tiebreaker when RS is equal.
Each signal type uses its own exit rules.

Usage:
    python download_cache.py
    python backtest_combined.py

Outputs:
    combined_trades.csv
    combined_summary.csv
    combined_equity_curve.csv
"""

from datetime import date
from pathlib import Path

import pandas as pd

from src.setup_rules import PullbackUptrendSetup, BreakoutSetup


CACHE_DIR = Path("cache")
SCAN_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

# Pullback exit rules
PULLBACK_STOP_PCT = 0.02
PULLBACK_TARGET_PCT = 0.07
PULLBACK_MAX_HOLD = 10

# Breakout exit rules
BREAKOUT_STOP_BUFFER_PCT = 0.005
BREAKOUT_MAX_HOLD = 40

OUTPUT_TRADES = Path("combined_trades.csv")
OUTPUT_SUMMARY = Path("combined_summary.csv")
OUTPUT_EQUITY = Path("combined_equity_curve.csv")


def load_universe_from_web_or_cache() -> list[str]:
    try:
        from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe

        sp500 = SP500UniverseStockAnalysis().tickers
        nasdaq = Nasdaq100Universe().tickers
        tickers = sorted(set(sp500 + nasdaq))
        print(f"Universe loaded from web: {len(tickers)} tickers")
        return tickers
    except Exception as exc:
        print(f"Universe download failed, using cached tickers instead: {exc}")
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
        print("SPY missing from cache; market filter disabled")
        return None

    spy = spy.copy()
    spy["SMA200"] = spy["Close"].rolling(200).mean()
    spy["High52"] = spy["Close"].rolling(252).max()
    return set(
        idx.date()
        for idx, row in spy.iterrows()
        if idx.year == scan_year
        and row["Close"] > row["SMA200"]
        and row["Close"] >= row["High52"] * 0.95
    )


def detect_all_signals(
    cache: dict,
    tickers: list[str],
    scan_year: int,
    pullback_setup: PullbackUptrendSetup,
    breakout_setup: BreakoutSetup,
) -> list[dict]:
    print(f"\nDetecting signals for {scan_year}...")
    valid_market_dates = build_market_filter(cache, scan_year)

    signals = []
    for i, ticker in enumerate(tickers, 1):
        df = cache.get(ticker)
        if df is None or len(df) < 230:
            continue

        try:
            # --- Pullback signals ---
            pb_prepared = pullback_setup.prepare(df)
            pb_applied = pullback_setup.apply(pb_prepared)
            pb_rows = pb_applied[
                pb_applied["signal"] &
                (pb_applied.index.year == scan_year)
            ]

            for idx, row in pb_rows.iterrows():
                signal_date = idx.date()
                if valid_market_dates is not None and signal_date not in valid_market_dates:
                    continue

                signals.append({
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "setup": "pullback",
                    "entry_price": float(row["Close"]),
                    "year": scan_year,
                    "relative_strength": calculate_rs_from_cache(ticker, signal_date, cache),
                    # Pullback-specific exit info
                    "stop_price": float(row["Close"]) * (1 - PULLBACK_STOP_PCT),
                    "target_price": float(row["Close"]) * (1 + PULLBACK_TARGET_PCT),
                    "base_low": None,
                    "resistance_level": None,
                    "base_height": None,
                })

            # --- Breakout signals ---
            bo_prepared = breakout_setup.prepare(df)
            bo_applied = breakout_setup.apply(bo_prepared)
            bo_rows = bo_applied[
                bo_applied["signal"] &
                (bo_applied.index.year == scan_year)
            ]

            for idx, row in bo_rows.iterrows():
                signal_date = idx.date()
                if valid_market_dates is not None and signal_date not in valid_market_dates:
                    continue

                entry_price = float(row["Close"])
                resistance = float(row["resistance_level"])
                base_low = float(row["base_low"])

                # Apply breakout filters
                if entry_price > resistance * 1.02:
                    continue
                risk_pct = (entry_price - base_low) / entry_price
                if risk_pct > 0.05:
                    continue

                signals.append({
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "setup": "breakout",
                    "entry_price": entry_price,
                    "year": scan_year,
                    "relative_strength": calculate_rs_from_cache(ticker, signal_date, cache),
                    # Breakout-specific exit info
                    "stop_price": base_low * (1 - BREAKOUT_STOP_BUFFER_PCT),
                    "target_price": resistance + float(row["base_height"]),
                    "base_low": base_low,
                    "resistance_level": resistance,
                    "base_height": float(row["base_height"]),
                })

        except Exception as exc:
            print(f"  {ticker}: {exc}")

        if i % 100 == 0:
            print(f"  [{i}/{len(tickers)}] scanned - {len(signals)} signals")

    print(f"  Raw signals found: {len(signals)}")
    return signals


def select_top_signals(signals: list[dict]) -> list[dict]:
    """Rank signals by RS each day, take top 1. Breakout gets +10 RS bonus."""
    df = pd.DataFrame(signals)
    if df.empty:
        return []

    # Tiebreaker: breakout = 1, pullback = 0
    df["setup_priority"] = (df["setup"] == "breakout").astype(int)
    
    # Breakout gets +10 RS bonus to reflect higher win rate
    df["rs_adjusted"] = df["relative_strength"] + df["setup"].map({"breakout": 20, "pullback": 0})

    # Sort by date, then adjusted RS descending, then setup priority descending
    df = df.sort_values(
        ["signal_date", "rs_adjusted", "setup_priority"],
        ascending=[True, False, False]
    )

    # Take top 1 per day
    top = df.groupby("signal_date").first().reset_index()
    print(f"  Selected signals after daily ranking: {len(top)}")
    return top.to_dict("records")


def simulate_trade(signal: dict, cache: dict) -> dict | None:
    ticker = signal["ticker"]
    df = cache.get(ticker)
    if df is None:
        return None

    signal_date = signal["signal_date"]
    if isinstance(signal_date, str):
        signal_date = date.fromisoformat(signal_date)

    entry_price = signal["entry_price"]
    stop_price = signal["stop_price"]
    target_price = signal["target_price"]
    setup = signal["setup"]
    max_hold = PULLBACK_MAX_HOLD if setup == "pullback" else BREAKOUT_MAX_HOLD

    if stop_price <= 0 or target_price <= entry_price or stop_price >= entry_price:
        return None

    future = df[df.index.date > signal_date].head(max_hold)
    if future.empty:
        return None

    exit_price = None
    exit_date = None
    exit_reason = None
    days_held = 0

    for i, (idx, row) in enumerate(future.iterrows(), 1):
        days_held = i
        low = float(row["Low"])
        high = float(row["High"])
        close = float(row["Close"])

        if low <= stop_price and high >= target_price:
            exit_price = stop_price
            exit_date = idx.date()
            exit_reason = "Stop Loss"
            break
        if low <= stop_price:
            exit_price = stop_price
            exit_date = idx.date()
            exit_reason = "Stop Loss"
            break
        if high >= target_price:
            exit_price = target_price
            exit_date = idx.date()
            exit_reason = "Profit Target"
            break
        if i >= max_hold:
            exit_price = close
            exit_date = idx.date()
            exit_reason = "Time Exit"
            break

    if exit_price is None:
        return None

    pnl = (exit_price - entry_price) / entry_price

    return {
        "ticker": ticker,
        "signal_date": signal_date.isoformat(),
        "setup": setup,
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "target_price": round(target_price, 2),
        "exit_date": exit_date.isoformat(),
        "exit_price": round(exit_price, 2),
        "exit_reason": exit_reason,
        "days_held": days_held,
        "pnl": round(pnl, 6),
        "win": pnl > 0,
        "relative_strength": signal["relative_strength"],
        "year": signal["year"],
    }


def build_equity_curve(trades: pd.DataFrame) -> pd.DataFrame:
    curve = trades.sort_values(["exit_date", "signal_date", "ticker"]).copy()
    equity = 1.0
    rows = []
    for _, trade in curve.iterrows():
        equity *= 1 + float(trade["pnl"])
        rows.append({
            "date": trade["exit_date"],
            "ticker": trade["ticker"],
            "pnl": trade["pnl"],
            "equity": equity,
        })
    return pd.DataFrame(rows)


def max_drawdown(equity_curve: pd.DataFrame) -> float:
    if equity_curve.empty:
        return 0.0
    equity = equity_curve["equity"].astype(float)
    running_high = equity.cummax()
    drawdown = (equity / running_high) - 1
    return float(drawdown.min())


def summarize(trades: pd.DataFrame, equity_curve: pd.DataFrame) -> pd.DataFrame:
    winners = trades[trades["pnl"] > 0]
    losers = trades[trades["pnl"] <= 0]

    rows = [{
        "total_trades": len(trades),
        "win_rate": round(float(trades["win"].mean()) * 100, 2),
        "avg_return": round(float(trades["pnl"].mean()) * 100, 2),
        "avg_winner_return": round(float(winners["pnl"].mean()) * 100, 2) if not winners.empty else None,
        "avg_loser_return": round(float(losers["pnl"].mean()) * 100, 2) if not losers.empty else None,
        "max_drawdown": round(max_drawdown(equity_curve) * 100, 2),
        "pullback_trades": len(trades[trades["setup"] == "pullback"]),
        "breakout_trades": len(trades[trades["setup"] == "breakout"]),
    }]

    for year, subset in trades.groupby("year"):
        year_curve = build_equity_curve(subset)
        year_winners = subset[subset["pnl"] > 0]
        year_losers = subset[subset["pnl"] <= 0]
        rows.append({
            "total_trades": len(subset),
            "win_rate": round(float(subset["win"].mean()) * 100, 2),
            "avg_return": round(float(subset["pnl"].mean()) * 100, 2),
            "avg_winner_return": round(float(year_winners["pnl"].mean()) * 100, 2) if not year_winners.empty else None,
            "avg_loser_return": round(float(year_losers["pnl"].mean()) * 100, 2) if not year_losers.empty else None,
            "max_drawdown": round(max_drawdown(year_curve) * 100, 2),
            "pullback_trades": len(subset[subset["setup"] == "pullback"]),
            "breakout_trades": len(subset[subset["setup"] == "breakout"]),
            "year": year,
        })

    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("  Combined Strategy Backtest")
    print("=" * 60 + "\n")

    tickers = load_universe_from_web_or_cache()
    cache = load_price_cache(tickers)

    pullback_setup = PullbackUptrendSetup(
        pullback_pct=0.02,
        use_volume=True,
        reclaim_pct=0.0,
        require_sma200=False,
        use_rsi=False,
    )

    breakout_setup = BreakoutSetup(
        min_base_days=15,
        max_base_days=30,
        max_range_pct=0.05,
        near_resistance_pct=0.03,
        volume_ratio_min=1.5,
        breakout_only=True,
    )

    all_signals = []
    for year in SCAN_YEARS:
        all_signals.extend(detect_all_signals(cache, tickers, year, pullback_setup, breakout_setup))

    print(f"\nTotal raw signals: {len(all_signals)}")
    if not all_signals:
        print("No signals found.")
        return

    top_signals = select_top_signals(all_signals)

    trades = []
    for signal in top_signals:
        trade = simulate_trade(signal, cache)
        if trade:
            trades.append(trade)

    if not trades:
        print("No completed trades to summarize.")
        return

    trades_df = pd.DataFrame(trades)
    equity_curve = build_equity_curve(trades_df)
    summary = summarize(trades_df, equity_curve)

    trades_df.to_csv(OUTPUT_TRADES, index=False)
    summary.to_csv(OUTPUT_SUMMARY, index=False)
    equity_curve.to_csv(OUTPUT_EQUITY, index=False)

    print(f"\nCompleted trades: {len(trades_df)}")
    print(summary.to_string(index=False))
    print(f"\nSaved: {OUTPUT_TRADES}")
    print(f"Saved: {OUTPUT_SUMMARY}")
    print(f"Saved: {OUTPUT_EQUITY}")


if __name__ == "__main__":
    main()