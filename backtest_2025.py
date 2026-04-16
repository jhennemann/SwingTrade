"""
backtest_2025.py

Scans every trading day across SCAN_YEARS, detects PullbackUptrendSetup signals,
simulates trade outcomes, and analyzes win rate by RS threshold.

Reads price data from the cache/ folder — run download_cache.py first.
Make sure DOWNLOAD_START in download_cache.py is early enough for all years
(e.g. "2022-01-01" to cover 2023-2025 with warm SMAs).

Usage:
    python download_cache.py   # once, or to refresh prices
    python backtest_2025.py    # as many times as you want

Output:
    backtest_summary.csv  — win rate / avg P&L by year, RS threshold, entry mode, stop loss
"""

from datetime import date
from pathlib import Path

import pandas as pd

from src.setup_rules import PullbackUptrendSetup
from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe

# ── Config ─────────────────────────────────────────────────────────────────────
CACHE_DIR    = Path("cache")    # populated by download_cache.py
SCAN_YEARS   = [2023, 2024, 2025]

PROFIT_TARGET    = 0.07
MAX_DAYS         = 10
RS_LOOKBACK      = 60              # Trading days for RS calculation

ENTRY_MODE   = "open"   # fixed: next day open
STOP_LOSS    = 0.02
PROFIT_TARGET = 0.07

RS_THRESHOLDS  = [0, 10, 20, 30, 40, 50, 60, 70, 80]
SIL_THRESHOLDS = [1, 2, 3, 4, 5]  # signals_in_lookback — max allowed (lower = rarer setup)

OUTPUT_SUMMARY   = Path("backtest_summary.csv")



# ── Universe ───────────────────────────────────────────────────────────────────
def load_universe() -> list[str]:
    print("Loading universe...")
    sp500   = SP500UniverseStockAnalysis().tickers
    nasdaq  = Nasdaq100Universe().tickers
    combined = sorted(set(sp500 + nasdaq))
    print(f"  S&P 500: {len(sp500)} | NASDAQ 100: {len(nasdaq)} | Combined: {len(combined)}\n")
    return combined


# ── Price Cache ────────────────────────────────────────────────────────────────
def load_price_cache(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    Load OHLCV data from cache/ folder (populated by download_cache.py).
    Returns dict: ticker -> DataFrame with DatetimeIndex.
    """
    if not CACHE_DIR.exists():
        raise FileNotFoundError(
            f"Cache folder '{CACHE_DIR}' not found. Run download_cache.py first."
        )

    print(f"Loading price data from {CACHE_DIR}/...")
    cache  = {}
    missing = []

    all_tickers = list(tickers) + (["SPY"] if "SPY" not in tickers else [])

    for ticker in all_tickers:
        path = CACHE_DIR / f"{ticker}.csv"
        if not path.exists():
            missing.append(ticker)
            continue
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            cache[ticker] = df
        except Exception as e:
            missing.append(ticker)
            print(f"  ⚠ {ticker}: {e}")

    print(f"  Loaded: {len(cache)} tickers | Missing: {len(missing)}")
    if missing:
        print(f"  Missing: {missing[:20]}{'...' if len(missing) > 20 else ''}")
        print(f"  Run download_cache.py to fetch missing tickers.\n")

    return cache


# ── RS Calculation (point-in-time) ─────────────────────────────────────────────
def calc_rs_at_date(ticker: str, signal_date: date, cache: dict) -> float:
    """
    Compute RS as of signal_date using cached data.
    RS = (stock 60-day return - SPY 60-day return) * 100
    """
    try:
        stock_df = cache.get(ticker)
        spy_df   = cache.get("SPY")

        if stock_df is None or spy_df is None:
            return 0.0

        # Get rows up to and including signal_date
        stock_hist = stock_df[stock_df.index.date <= signal_date]["Close"].dropna()
        spy_hist   = spy_df[spy_df.index.date <= signal_date]["Close"].dropna()

        if len(stock_hist) < RS_LOOKBACK or len(spy_hist) < RS_LOOKBACK:
            return 0.0

        stock_return = (stock_hist.iloc[-1] / stock_hist.iloc[-RS_LOOKBACK]) - 1
        spy_return   = (spy_hist.iloc[-1]   / spy_hist.iloc[-RS_LOOKBACK])   - 1

        return float((stock_return - spy_return) * 100)

    except Exception:
        return 0.0


# ── Signal Detection ───────────────────────────────────────────────────────────
def build_spy_market_filter(cache: dict, scan_year: int) -> set[date]:
    """
    Returns a set of dates in scan_year where SPY Close > SMA200.
    Only these dates pass the market filter.
    """
    spy_df = cache.get("SPY")
    if spy_df is None:
        print("  ⚠ SPY not in cache — market filter disabled")
        return None

    spy_df = spy_df.copy()
    spy_df["SMA200"] = spy_df["Close"].rolling(200).mean()

    valid_dates = set(
        idx.date()
        for idx, row in spy_df.iterrows()
        if idx.year == scan_year and row["Close"] > row["SMA200"]
    )

    total_days = sum(1 for idx in spy_df.index if idx.year == scan_year)
    print(f"  SPY market filter: {len(valid_dates)}/{total_days} trading days in {scan_year} pass (SPY > SMA200)")
    return valid_dates


def detect_signals(cache: dict, tickers: list[str], scan_year: int) -> list[dict]:
    """
    Run PullbackUptrendSetup on every ticker and collect signals in scan_year.
    Applies SPY SMA200 market filter — no signals taken on days SPY is below SMA200.
    Returns list of dicts: ticker, signal_date, rs.
    """
    print(f"\nDetecting signals for {scan_year}...")

    # Build market filter upfront
    valid_market_dates = build_spy_market_filter(cache, scan_year)

    setup = PullbackUptrendSetup(pullback_pct=0.02, use_volume=True)

    all_signals = []
    filtered_out = 0

    for i, ticker in enumerate(tickers, 1):
        df = cache.get(ticker)
        if df is None or len(df) < 60:
            continue

        try:
            df_prep   = setup.prepare(df)
            df_signal = setup.apply(df_prep)

            # Filter to signal rows within scan_year
            mask = (
                df_signal["signal"] &
                (df_signal.index.year == scan_year)
            )
            signal_rows = df_signal[mask]

            for idx in signal_rows.index:
                signal_date = idx.date()

                # SPY market filter
                if valid_market_dates is not None and signal_date not in valid_market_dates:
                    filtered_out += 1
                    continue

                rs = calc_rs_at_date(ticker, signal_date, cache)
                # signals_in_lookback = total signals for this ticker in its full history up to signal_date
                sil = int(df_signal[df_signal.index.date <= signal_date]["signal"].sum())
                all_signals.append({
                    "ticker":      ticker,
                    "signal_date": signal_date,
                    "rs":          rs,
                    "sil":         sil,
                    "year":        scan_year,
                })

        except Exception as e:
            print(f"  ⚠ {ticker} signal detection: {e}")

        if i % 100 == 0:
            print(f"  [{i}/{len(tickers)}] scanned — {len(all_signals)} signals so far")

    print(f"  Total signals found in {scan_year}: {len(all_signals)} ({filtered_out} filtered out by SPY SMA200)")
    return all_signals


# ── Trade Simulation ───────────────────────────────────────────────────────────
def simulate_trade(
    ticker: str,
    signal_date: date,
    cache: dict,
    stop_loss: float = 0.02,
    entry_mode: str = "open",
    profit_target: float = 0.07,
) -> dict | None:
    """
    Simulate entry/exit from cache.

    entry_mode = "open"  — entry at next day open, exit at day-after-trigger open (realistic)
    entry_mode = "close" — entry at signal day close, exit at close on trigger day (theoretical)
    """
    df = cache.get(ticker)
    if df is None:
        return None

    try:
        if entry_mode == "close":
            # Entry: close on the signal day itself
            signal_rows = df[df.index.date == signal_date]
            if signal_rows.empty:
                return None
            entry_date  = signal_date
            entry_price = float(signal_rows.iloc[0]["Close"])
            # Hold days start the next trading day
            holding = df[df.index.date > signal_date].head(MAX_DAYS)
        else:
            # Entry: open of the first trading day after signal_date
            future = df[df.index.date > signal_date]
            if future.empty:
                return None
            entry_date  = future.index[0].date()
            entry_price = float(future.iloc[0]["Open"])
            # Hold days start the day after entry
            holding = df[df.index.date > entry_date].head(MAX_DAYS + 1)

        if entry_price <= 0:
            return None

        stop_price   = entry_price * (1 - stop_loss)
        target_price = entry_price * (1 + profit_target)

        exit_price  = None
        exit_date   = None
        exit_reason = None
        days_held   = 0

        for j, (idx, row) in enumerate(holding.iterrows()):
            days_held = j + 1
            low   = float(row["Low"])
            high  = float(row["High"])
            close = float(row["Close"])

            if entry_mode == "close":
                # Exit at close on the day the condition is triggered
                if low <= stop_price:
                    exit_price  = close
                    exit_date   = idx.date()
                    exit_reason = "Stop Loss"
                    break
                if high >= target_price:
                    exit_price  = close
                    exit_date   = idx.date()
                    exit_reason = "Profit Target"
                    break
                if days_held >= MAX_DAYS:
                    exit_price  = close
                    exit_date   = idx.date()
                    exit_reason = "Time Exit"
                    break
            else:
                # Exit at next day open after condition triggers
                if low <= stop_price:
                    nxt = df[df.index.date > idx.date()]
                    exit_price  = float(nxt.iloc[0]["Open"]) if not nxt.empty else stop_price
                    exit_date   = nxt.index[0].date() if not nxt.empty else idx.date()
                    exit_reason = "Stop Loss"
                    break
                if high >= target_price:
                    nxt = df[df.index.date > idx.date()]
                    exit_price  = float(nxt.iloc[0]["Open"]) if not nxt.empty else target_price
                    exit_date   = nxt.index[0].date() if not nxt.empty else idx.date()
                    exit_reason = "Profit Target"
                    break
                if days_held >= MAX_DAYS:
                    nxt = df[df.index.date > idx.date()]
                    exit_price  = float(nxt.iloc[0]["Open"]) if not nxt.empty else close
                    exit_date   = nxt.index[0].date() if not nxt.empty else idx.date()
                    exit_reason = "Time Exit"
                    break

        if exit_price is None:
            return None

        pnl = (exit_price - entry_price) / entry_price

        return {
            "ticker":       ticker,
            "signal_date":  signal_date.isoformat(),
            "entry_date":   entry_date.isoformat(),
            "entry_price":  round(entry_price, 2),
            "exit_date":    exit_date.isoformat(),
            "exit_price":   round(exit_price, 2),
            "days_held":    days_held,
            "pnl":          round(pnl, 6),
            "exit_reason":  exit_reason,
            "win":          pnl > 0,
        }

    except Exception as e:
        print(f"  ⚠ simulate {ticker} ({signal_date}): {e}")
        return None


# ── RS Bucket Summary ──────────────────────────────────────────────────────────
def summarize_by_rs(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each RS threshold, compute win rate, avg P&L, and exit reason breakdown.
    """
    rows = []
    for threshold in RS_THRESHOLDS:
        subset = df[df["rs"] >= threshold]
        if subset.empty:
            rows.append({
                "rs_min":          threshold,
                "n_trades":        0,
                "win_rate":        None,
                "avg_pnl":         None,
                "n_stop":          0,
                "n_target":        0,
                "n_time":          0,
                "avg_pnl_stop":    None,
                "avg_pnl_target":  None,
                "avg_pnl_time":    None,
            })
            continue

        stops   = subset[subset["exit_reason"] == "Stop Loss"]
        targets = subset[subset["exit_reason"] == "Profit Target"]
        time_ex = subset[subset["exit_reason"] == "Time Exit"]

        rows.append({
            "rs_min":          threshold,
            "n_trades":        len(subset),
            "win_rate":        round(subset["win"].mean() * 100, 1),
            "avg_pnl":         round(subset["pnl"].mean() * 100, 2),
            "n_stop":          len(stops),
            "n_target":        len(targets),
            "n_time":          len(time_ex),
            "avg_pnl_stop":    round(stops["pnl"].mean() * 100, 2) if not stops.empty else None,
            "avg_pnl_target":  round(targets["pnl"].mean() * 100, 2) if not targets.empty else None,
            "avg_pnl_time":    round(time_ex["pnl"].mean() * 100, 2) if not time_ex.empty else None,
        })

    return pd.DataFrame(rows)


def print_rs_table(summary_df: pd.DataFrame):
    """Print compact win rate / avg P&L table."""
    print(f"{'RS ≥':<8} {'Trades':<10} {'Win Rate':<12} {'Avg P&L'}")
    print("-" * 45)
    for _, row in summary_df.iterrows():
        if row["n_trades"] == 0:
            print(f"{int(row['rs_min']):<8} {'0':<10} {'—':<12} {'—'}")
        else:
            print(
                f"{int(row['rs_min']):<8} "
                f"{int(row['n_trades']):<10} "
                f"{row['win_rate']:.1f}%{'':<7} "
                f"{row['avg_pnl']:+.2f}%"
            )


def print_exit_breakdown(summary_df: pd.DataFrame, label: str = ""):
    """Print a second table showing exit reason counts and avg P&L per reason."""
    print(f"\n{'=' * 75}")
    print(f"  Exit Reason Breakdown — {label}")
    print(f"{'=' * 75}")
    print(f"{'RS ≥':<8} {'Trades':<8} {'Stops':<8} {'Stop P&L':<12} {'Targets':<10} {'Target P&L':<13} {'Time':<7} {'Time P&L'}")
    print("-" * 75)
    for _, row in summary_df.iterrows():
        if row["n_trades"] == 0:
            continue

        def fmt(val):
            return f"{val:+.2f}%" if val is not None else "—"

        print(
            f"{int(row['rs_min']):<8}"
            f"{int(row['n_trades']):<8}"
            f"{int(row['n_stop']):<8}"
            f"{fmt(row['avg_pnl_stop']):<12}"
            f"{int(row['n_target']):<10}"
            f"{fmt(row['avg_pnl_target']):<13}"
            f"{int(row['n_time']):<7}"
            f"{fmt(row['avg_pnl_time'])}"
        )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print(f"  SwingTrade Backtest — {', '.join(str(y) for y in SCAN_YEARS)}")
    print("=" * 60 + "\n")

    # 1. Universe
    tickers = load_universe()

    # 2. Load price cache
    cache = load_price_cache(tickers)

    # 3. Detect signals across all years
    all_signals = []
    for year in SCAN_YEARS:
        year_signals = detect_signals(cache, tickers, scan_year=year)
        all_signals.extend(year_signals)

    print(f"\nTotal signals across all years: {len(all_signals)}")

    if not all_signals:
        print("No signals found — check setup_rules or date range.")
        return

    # 4. Simulate all trades once with fixed stop/target
    print(f"\nSimulating {len(all_signals)} trades (Target={PROFIT_TARGET:.0%} | Stop={STOP_LOSS:.0%})...")
    trades = []
    for sig in all_signals:
        trade = simulate_trade(
            sig["ticker"], sig["signal_date"], cache,
            stop_loss=STOP_LOSS, entry_mode=ENTRY_MODE,
            profit_target=PROFIT_TARGET,
        )
        if trade:
            trade["rs"]   = sig["rs"]
            trade["sil"]  = sig["sil"]
            trade["year"] = sig["year"]
            trades.append(trade)

    print(f"  Simulated: {len(trades)} trades")

    if not trades:
        print("No trades to analyze.")
        return

    trades_df = pd.DataFrame(trades)

    # 5. Print RS threshold table (all signals, no SIL filter)
    print(f"\n{'=' * 60}")
    print(f"  Win Rate by RS Threshold — ALL YEARS (no SIL filter)")
    print(f"{'=' * 60}")
    print_rs_table(summarize_by_rs(trades_df))

    # 6. Print SIL filter tables
    print(f"\n{'=' * 60}")
    print(f"  Win Rate by RS Threshold — filtered by Signals in Lookback")
    print(f"{'=' * 60}")
    for max_sil in SIL_THRESHOLDS:
        subset = trades_df[trades_df["sil"] <= max_sil]
        if subset.empty:
            continue
        print(f"\n  SIL ≤ {max_sil} ({len(subset)} trades)")
        print("-" * 45)
        print_rs_table(summarize_by_rs(subset))

    # 7. Save summary
    all_summaries = []
    base = summarize_by_rs(trades_df)
    base["sil_filter"] = "none"
    all_summaries.append(base)
    for max_sil in SIL_THRESHOLDS:
        subset = trades_df[trades_df["sil"] <= max_sil]
        if not subset.empty:
            s = summarize_by_rs(subset)
            s["sil_filter"] = f"<={max_sil}"
            all_summaries.append(s)

    combined = pd.concat(all_summaries, ignore_index=True)
    combined.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\n✓ Summary saved to {OUTPUT_SUMMARY}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()