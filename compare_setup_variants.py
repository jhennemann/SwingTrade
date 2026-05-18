"""
Compare pullback setup rule variants against cached 2023-2025 data.

This runner is intentionally offline: it uses tickers already present in cache/
instead of downloading the current S&P 500 / Nasdaq 100 universe.
"""

from datetime import date
from pathlib import Path

import pandas as pd

from src.setup_rules import PullbackUptrendSetup


CACHE_DIR = Path("cache")
SCAN_YEARS = [2023, 2024, 2025]
MAX_DAYS = 10
RS_LOOKBACK = 60
ENTRY_MODE = "open"
STOP_LOSS = 0.02
PROFIT_TARGET = 0.07
RS_THRESHOLDS = [0, 10, 20, 30, 40, 50, 60, 70, 80]

VARIANTS = [
    {
        "name": "baseline",
        "setup": {"pullback_pct": 0.02, "use_volume": True},
    },
    {
        "name": "no_volume_filter",
        "setup": {"pullback_pct": 0.02, "use_volume": False},
    },
    {
        "name": "pullback_1pct",
        "setup": {"pullback_pct": 0.01, "use_volume": True},
    },
    {
        "name": "reclaim_0_5pct",
        "setup": {"pullback_pct": 0.02, "use_volume": True, "reclaim_pct": 0.005},
    },
    {
        "name": "require_sma200",
        "setup": {"pullback_pct": 0.02, "use_volume": True, "require_sma200": True},
    },
]


def load_cached_tickers() -> list[str]:
    tickers = sorted(path.stem for path in CACHE_DIR.glob("*.csv"))
    return [ticker for ticker in tickers if ticker != "SPY"]


def load_price_cache(tickers: list[str]) -> dict[str, pd.DataFrame]:
    cache = {}
    all_tickers = list(tickers) + (["SPY"] if "SPY" not in tickers else [])

    for ticker in all_tickers:
        path = CACHE_DIR / f"{ticker}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df["_date"] = df.index.date
        df["_year"] = df.index.year
        cache[ticker] = df

    return cache


def calc_atr(df: pd.DataFrame, signal_date: date, period: int = 14) -> float | None:
    hist = df[df["_date"] <= signal_date].tail(period + 1)
    if len(hist) < period + 1:
        return None

    high = hist["High"].astype(float)
    low = hist["Low"].astype(float)
    close = hist["Close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return float(tr.iloc[1:].mean())


def calc_rs_at_date(ticker: str, signal_date: date, cache: dict[str, pd.DataFrame]) -> float:
    stock_df = cache.get(ticker)
    spy_df = cache.get("SPY")
    if stock_df is None or spy_df is None:
        return 0.0

    stock_hist = stock_df[stock_df["_date"] <= signal_date]["Close"].dropna()
    spy_hist = spy_df[spy_df["_date"] <= signal_date]["Close"].dropna()
    if len(stock_hist) < RS_LOOKBACK or len(spy_hist) < RS_LOOKBACK:
        return 0.0

    stock_return = (stock_hist.iloc[-1] / stock_hist.iloc[-RS_LOOKBACK]) - 1
    spy_return = (spy_hist.iloc[-1] / spy_hist.iloc[-RS_LOOKBACK]) - 1
    return float((stock_return - spy_return) * 100)


def build_spy_market_filter(cache: dict[str, pd.DataFrame], scan_year: int) -> set[date] | None:
    spy_df = cache.get("SPY")
    if spy_df is None:
        return None

    spy_df = spy_df.copy()
    spy_df["SMA200"] = spy_df["Close"].rolling(200).mean()
    return {
        idx.date()
        for idx, row in spy_df.iterrows()
        if row["_year"] == scan_year and row["Close"] > row["SMA200"]
    }


def detect_signals(
    cache: dict[str, pd.DataFrame],
    tickers: list[str],
    scan_year: int,
    setup_kwargs: dict,
) -> list[dict]:
    valid_market_dates = build_spy_market_filter(cache, scan_year)
    setup = PullbackUptrendSetup(**setup_kwargs)
    all_signals = []

    for ticker in tickers:
        df = cache.get(ticker)
        if df is None or len(df) < 200:
            continue

        df_prep = setup.prepare(df)
        df_signal = setup.apply(df_prep)
        signal_rows = df_signal[df_signal["signal"] & (df_signal["_year"] == scan_year)]

        for idx in signal_rows.index:
            signal_date = idx.date()
            if valid_market_dates is not None and signal_date not in valid_market_dates:
                continue

            atr = calc_atr(df, signal_date)
            close_price = float(df[df["_date"] <= signal_date]["Close"].iloc[-1])
            if atr is None or (atr / close_price) > 0.03:
                continue

            sma50_vals = df_prep["SMA50"][df_prep["_date"] <= signal_date]
            if len(sma50_vals) >= 11:
                slope = (sma50_vals.iloc[-1] - sma50_vals.iloc[-11]) / sma50_vals.iloc[-11] * 100
            else:
                slope = None

            all_signals.append(
                {
                    "ticker": ticker,
                    "signal_date": signal_date,
                    "rs": calc_rs_at_date(ticker, signal_date, cache),
                    "sil": int(df_signal[df_signal["_date"] <= signal_date]["signal"].sum()),
                    "year": scan_year,
                    "sma50_slope": slope,
                }
            )

    return all_signals


def simulate_trade(
    ticker: str,
    signal_date: date,
    cache: dict[str, pd.DataFrame],
    stop_loss: float = STOP_LOSS,
    profit_target: float = PROFIT_TARGET,
) -> dict | None:
    df = cache.get(ticker)
    if df is None:
        return None

    future = df[df["_date"] > signal_date]
    if future.empty:
        return None

    entry_date = future.index[0].date()
    entry_price = float(future.iloc[0]["Open"])
    if entry_price <= 0:
        return None

    holding = df[df["_date"] > entry_date].head(MAX_DAYS + 1)
    stop_price = entry_price * (1 - stop_loss)
    target_price = entry_price * (1 + profit_target)

    for j, (idx, row) in enumerate(holding.iterrows()):
        days_held = j + 1
        low = float(row["Low"])
        high = float(row["High"])
        close = float(row["Close"])

        if low <= stop_price:
            nxt = df[df["_date"] > idx.date()]
            exit_price = float(nxt.iloc[0]["Open"]) if not nxt.empty else stop_price
            exit_date = nxt.index[0].date() if not nxt.empty else idx.date()
            exit_reason = "Stop Loss"
            break
        if high >= target_price:
            nxt = df[df["_date"] > idx.date()]
            exit_price = float(nxt.iloc[0]["Open"]) if not nxt.empty else target_price
            exit_date = nxt.index[0].date() if not nxt.empty else idx.date()
            exit_reason = "Profit Target"
            break
        if days_held >= MAX_DAYS:
            nxt = df[df["_date"] > idx.date()]
            exit_price = float(nxt.iloc[0]["Open"]) if not nxt.empty else close
            exit_date = nxt.index[0].date() if not nxt.empty else idx.date()
            exit_reason = "Time Exit"
            break
    else:
        return None

    pnl = (exit_price - entry_price) / entry_price
    return {
        "ticker": ticker,
        "signal_date": signal_date.isoformat(),
        "entry_date": entry_date.isoformat(),
        "entry_price": round(entry_price, 2),
        "exit_date": exit_date.isoformat(),
        "exit_price": round(exit_price, 2),
        "days_held": days_held,
        "pnl": round(pnl, 6),
        "exit_reason": exit_reason,
        "win": pnl > 0,
    }


def summarize_by_rs(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for threshold in RS_THRESHOLDS:
        subset = df[df["rs"] >= threshold]
        if subset.empty:
            rows.append(
                {
                    "rs_min": threshold,
                    "n_trades": 0,
                    "win_rate": None,
                    "avg_pnl": None,
                    "n_stop": 0,
                    "n_target": 0,
                    "n_time": 0,
                }
            )
            continue

        rows.append(
            {
                "rs_min": threshold,
                "n_trades": len(subset),
                "win_rate": round(subset["win"].mean() * 100, 1),
                "avg_pnl": round(subset["pnl"].mean() * 100, 2),
                "n_stop": int((subset["exit_reason"] == "Stop Loss").sum()),
                "n_target": int((subset["exit_reason"] == "Profit Target").sum()),
                "n_time": int((subset["exit_reason"] == "Time Exit").sum()),
            }
        )
    return pd.DataFrame(rows)


def run_variant(name: str, setup_kwargs: dict, cache: dict, tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_signals = []
    for year in SCAN_YEARS:
        all_signals.extend(detect_signals(cache, tickers, year, setup_kwargs))

    trades = []
    for sig in all_signals:
        trade = simulate_trade(sig["ticker"], sig["signal_date"], cache)
        if trade:
            trade.update(
                {
                    "variant": name,
                    "rs": sig["rs"],
                    "sil": sig["sil"],
                    "year": sig["year"],
                    "sma50_slope": sig["sma50_slope"],
                }
            )
            trades.append(trade)

    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return trades_df, pd.DataFrame()

    summary = summarize_by_rs(trades_df)
    summary.insert(0, "variant", name)
    return trades_df, summary


def make_headline(summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, group in summary.groupby("variant", sort=False):
        for rs_min in [0, 50, 60, 70]:
            row = group[group["rs_min"] == rs_min]
            if not row.empty:
                rows.append(row.iloc[0].to_dict())
    return pd.DataFrame(rows)


def main():
    print("=" * 70, flush=True)
    print("  Pullback Setup Variant Comparison", flush=True)
    print("=" * 70, flush=True)
    print(f"Years: {', '.join(str(y) for y in SCAN_YEARS)}", flush=True)
    print(f"Entry={ENTRY_MODE} | Stop={STOP_LOSS:.0%} | Target={PROFIT_TARGET:.0%}\n", flush=True)

    tickers = load_cached_tickers()
    cache = load_price_cache(tickers)
    print(f"Loaded {len(tickers)} cached tickers plus SPY", flush=True)

    all_trades = []
    all_summaries = []

    for variant in VARIANTS:
        print(f"\nRunning {variant['name']}: {variant['setup']}", flush=True)
        trades, summary = run_variant(variant["name"], variant["setup"], cache, tickers)
        if trades.empty:
            print("  No trades.", flush=True)
            continue

        all_trades.append(trades)
        all_summaries.append(summary)
        print(make_headline(summary).to_string(index=False), flush=True)

    if not all_summaries:
        print("\nNo variant results to save.", flush=True)
        return

    summary_df = pd.concat(all_summaries, ignore_index=True)
    headline_df = make_headline(summary_df)
    trades_df = pd.concat(all_trades, ignore_index=True)

    summary_df.to_csv("strategy_variant_summary.csv", index=False)
    headline_df.to_csv("strategy_variant_headline.csv", index=False)
    trades_df.to_csv("strategy_variant_trades.csv", index=False)

    print(f"\n{'=' * 70}", flush=True)
    print("  Final Headline Comparison", flush=True)
    print(f"{'=' * 70}", flush=True)
    print(headline_df.to_string(index=False), flush=True)
    print("\nSaved strategy_variant_summary.csv, strategy_variant_headline.csv, and strategy_variant_trades.csv", flush=True)


if __name__ == "__main__":
    main()
