"""
backtest_highmom.py

Historical 52-week high momentum strategy backtest using cached OHLCV data.

Usage:
    python download_cache.py
    python backtest_highmom.py

Outputs:
    highmom_trades.csv
    highmom_summary.csv
    highmom_equity_curve.csv
"""

from datetime import date
from pathlib import Path

import pandas as pd

from src.setup_rules import HighMomentumSetup


CACHE_DIR = Path("cache")
SCAN_YEARS = [2020, 2021, 2022, 2023, 2024, 2025]

STOP_LOSS_PCT = 0.02
PROFIT_TARGET_PCT = 0.15
MAX_HOLD_DAYS = 30

OUTPUT_TRADES = Path("highmom_trades.csv")
OUTPUT_SUMMARY = Path("highmom_summary.csv")
OUTPUT_EQUITY = Path("highmom_equity_curve.csv")


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
    return set(
        idx.date()
        for idx, row in spy.iterrows()
        if idx.year == scan_year and row["Close"] > row["SMA200"]
    )


def detect_highmom_signals(
    cache: dict,
    tickers: list[str],
    scan_year: int,
    setup: HighMomentumSetup,
) -> list[dict]:
    print(f"\nDetecting high momentum signals for {scan_year}...")
    valid_market_dates = build_market_filter(cache, scan_year)

    signals = []
    for i, ticker in enumerate(tickers, 1):
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

                signals.append({
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "entry_price": float(row["Close"]),
                    "high_52w": float(row["high_52w"]),
                    "volume_ratio": float(row["volume_ratio"]),
                    "year": scan_year,
                    "relative_strength": calculate_rs_from_cache(ticker, signal_date, cache),
                })
        except Exception as exc:
            print(f"  {ticker}: {exc}")

        if i % 100 == 0:
            print(f"  [{i}/{len(tickers)}] scanned - {len(signals)} signals")

    print(f"  Signals found: {len(signals)}")
    return signals


def simulate_trade(signal: dict, cache: dict) -> dict | None:
    ticker = signal["ticker"]
    df = cache.get(ticker)
    if df is None:
        return None

    signal_date = signal["signal_date"]

    future = df[df.index.date > signal_date].head(MAX_HOLD_DAYS + 1)
    if future.empty or len(future) < 2:
        return None

    # Enter at next day's open
    entry_price = float(future.iloc[0]["Open"])
    if entry_price <= 0:
        return None

    stop_price = entry_price * (1 - STOP_LOSS_PCT)
    target_price = entry_price * (1 + PROFIT_TARGET_PCT)

    trading_days = future.iloc[1:]

    exit_price = None
    exit_date = None
    exit_reason = None
    days_held = 0

    for i, (idx, row) in enumerate(trading_days.iterrows(), 1):
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
        if i >= MAX_HOLD_DAYS:
            exit_price = close
            exit_date = idx.date()
            exit_reason = "Time Exit"
            break

    if exit_price is None:
        return None

    pnl = (exit_price - entry_price) / entry_price
    risk = entry_price - stop_price
    reward = target_price - entry_price

    return {
        "ticker": ticker,
        "signal_date": signal_date.isoformat(),
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "target_price": round(target_price, 2),
        "high_52w": round(signal["high_52w"], 2),
        "volume_ratio": round(signal["volume_ratio"], 3),
        "exit_date": exit_date.isoformat(),
        "exit_price": round(exit_price, 2),
        "exit_reason": exit_reason,
        "days_held": days_held,
        "pnl": round(pnl, 6),
        "win": pnl > 0,
        "risk_reward": round(reward / risk, 3),
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
        "avg_risk_reward": round(float(trades["risk_reward"].mean()), 2),
        "max_drawdown": round(max_drawdown(equity_curve) * 100, 2),
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
            "avg_risk_reward": round(float(subset["risk_reward"].mean()), 2),
            "max_drawdown": round(max_drawdown(year_curve) * 100, 2),
            "year": year,
        })

    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("  52-Week High Momentum Strategy Backtest")
    print("=" * 60 + "\n")

    tickers = load_universe_from_web_or_cache()
    cache = load_price_cache(tickers)

    setup = HighMomentumSetup(
        near_high_pct=0.02,
        volume_ratio_min=1.75,
        lookback_days=252,
    )

    all_signals = []
    for year in SCAN_YEARS:
        all_signals.extend(detect_highmom_signals(cache, tickers, year, setup))

    print(f"\nTotal signals: {len(all_signals)}")
    if not all_signals:
        print("No signals found.")
        return

    trades = []
    for signal in all_signals:
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