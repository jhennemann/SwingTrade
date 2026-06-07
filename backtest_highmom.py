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

COOLDOWN_DAYS = 10  # trading days to block re-entry after a stop loss


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

def apply_cooldown_filter(signals: list[dict], trades: list[dict], cooldown_days: int) -> list[dict]:
    """
    Remove signals where the same ticker had a stop-loss exit within
    cooldown_days calendar days prior to the signal date.
    """
    from datetime import timedelta

    # Build a lookup: ticker -> list of stop-loss exit dates
    stop_exits = {}
    for t in trades:
        if t["exit_reason"] == "Stop Loss":
            ticker = t["ticker"]
            exit_date = date.fromisoformat(t["exit_date"])
            stop_exits.setdefault(ticker, []).append(exit_date)

    filtered = []
    skipped = 0
    for signal in signals:
        ticker = signal["ticker"]
        signal_date = signal["signal_date"]
        exits = stop_exits.get(ticker, [])

        too_soon = any(
            0 < (signal_date - ex).days <= cooldown_days * 1.4  # ~1.4x to approximate trading days
            for ex in exits
        )

        if too_soon:
            skipped += 1
        else:
            filtered.append(signal)

    print(f"  Cooldown filter: {skipped} signals removed, {len(filtered)} remaining")
    return filtered

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

    print(f"\nTotal signals (before cooldown): {len(all_signals)}")
    if not all_signals:
        print("No signals found.")
        return

    # --- Baseline run (no cooldown) ---
    print("\n--- Baseline (no cooldown) ---")
    baseline_trades = [t for s in all_signals if (t := simulate_trade(s, cache))]
    baseline_df = pd.DataFrame(baseline_trades)
    baseline_equity = build_equity_curve(baseline_df)
    baseline_summary = summarize(baseline_df, baseline_equity)
    print(baseline_summary.to_string(index=False))

    # --- Cooldown run ---
    print(f"\n--- With {COOLDOWN_DAYS}-day cooldown after stop loss ---")
    filtered_signals = apply_cooldown_filter(all_signals, baseline_trades, COOLDOWN_DAYS)
    cooldown_trades = [t for s in filtered_signals if (t := simulate_trade(s, cache))]
    cooldown_df = pd.DataFrame(cooldown_trades)
    cooldown_equity = build_equity_curve(cooldown_df)
    cooldown_summary = summarize(cooldown_df, cooldown_equity)
    print(cooldown_summary.to_string(index=False))

    # Save cooldown version as primary output
    cooldown_df.to_csv(OUTPUT_TRADES, index=False)
    cooldown_summary.to_csv(OUTPUT_SUMMARY, index=False)
    cooldown_equity.to_csv(OUTPUT_EQUITY, index=False)

    baseline_df.to_csv("highmom_trades_baseline.csv", index=False)

    print(f"\nSaved cooldown trades → {OUTPUT_TRADES}")
    print(f"Saved baseline trades → highmom_trades_baseline.csv")

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

    print(f"\nTotal signals (before cooldown): {len(all_signals)}")
    if not all_signals:
        print("No signals found.")
        return

    # --- Baseline run (no cooldown) ---
    print("\n--- Baseline (no cooldown) ---")
    baseline_trades = [t for s in all_signals if (t := simulate_trade(s, cache))]
    baseline_df = pd.DataFrame(baseline_trades)
    baseline_equity = build_equity_curve(baseline_df)
    baseline_summary = summarize(baseline_df, baseline_equity)
    print(baseline_summary.to_string(index=False))

    # --- Option A: Require actual new high ---
    print("\n--- Option A: Require new 52-week high (Close > prior high) ---")
    setup_a = HighMomentumSetup(
        near_high_pct=0.0,
        volume_ratio_min=1.75,
        lookback_days=252,
    )
    signals_a = []
    for year in SCAN_YEARS:
        signals_a.extend(detect_highmom_signals(cache, tickers, year, setup_a))
    print(f"Signals: {len(signals_a)}")
    trades_a = [t for s in signals_a if (t := simulate_trade(s, cache))]
    df_a = pd.DataFrame(trades_a)
    equity_a = build_equity_curve(df_a)
    print(summarize(df_a, equity_a).to_string(index=False))

    # --- Option B: Tighten near_high_pct to 0.5% ---
    print("\n--- Option B: Within 0.5% of 52-week high ---")
    setup_b = HighMomentumSetup(
        near_high_pct=0.005,
        volume_ratio_min=1.75,
        lookback_days=252,
    )
    signals_b = []
    for year in SCAN_YEARS:
        signals_b.extend(detect_highmom_signals(cache, tickers, year, setup_b))
    print(f"Signals: {len(signals_b)}")
    trades_b = [t for s in signals_b if (t := simulate_trade(s, cache))]
    df_b = pd.DataFrame(trades_b)
    equity_b = build_equity_curve(df_b)
    print(summarize(df_b, equity_b).to_string(index=False))

    baseline_df.to_csv("highmom_trades_baseline.csv", index=False)

    print(f"\nSaved cooldown trades → {OUTPUT_TRADES}")
    print(f"Saved baseline trades → highmom_trades_baseline.csv")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()