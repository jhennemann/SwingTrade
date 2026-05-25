"""
paper_trade_manager.py

Manages paper trading for the 52-Week High Momentum strategy.
Two independent accounts (conservative, aggressive), each starting at $1,000.
Max 2 simultaneous positions per account at $500 each (dynamic sizing).

Called from main.py after the HighMomentumSetup scan runs.

Usage in main.py:
    from paper_trade_manager import run_paper_trading
    run_paper_trading(highmom_signals, supabase, today)

Where highmom_signals is a DataFrame with columns:
    ticker, relative_strength, rank, last_date
Already filtered for RS > 50 and sorted by relative_strength descending.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta


# ── Config ─────────────────────────────────────────────────────────────────────

CONFIGS = {
    "conservative": {
        "stop_pct":    0.02,   # 2% stop loss
        "target_pct":  0.07,   # 7% profit target
        "max_days":    10,     # max trading days held
    },
    "aggressive": {
        "stop_pct":    0.02,   # 2% stop loss
        "target_pct":  0.15,   # 15% profit target
        "max_days":    20,     # max trading days held
    },
}

MAX_SLOTS       = 2
STARTING_EQUITY = 1000.00


# ── Supabase helpers ───────────────────────────────────────────────────────────

def get_open_trades(supabase, config: str) -> list[dict]:
    """Fetch all open trades for a given config."""
    res = (
        supabase.table("paper_trades")
        .select("*")
        .eq("config", config)
        .eq("status", "open")
        .execute()
    )
    return res.data or []


def get_account_summary(supabase, config: str) -> dict:
    """
    Fetch pre-computed account summary from the Supabase view.
    Returns available_cash, open_slots, current_equity.
    """
    res = (
        supabase.table("paper_account_summary")
        .select("*")
        .eq("config", config)
        .execute()
    )
    if res.data:
        return res.data[0]
    # Fallback if view returns nothing (no trades yet)
    return {
        "config":          config,
        "starting_equity": STARTING_EQUITY,
        "closed_pnl":      0.0,
        "open_cost_basis": 0.0,
        "open_slots":      0,
        "available_cash":  STARTING_EQUITY,
        "current_equity":  STARTING_EQUITY,
    }


# ── Price helpers ──────────────────────────────────────────────────────────────

def get_next_day_open(ticker: str, after_date: date) -> float | None:
    """
    Fetch the next trading day's open price after after_date.
    Downloads a 7-day window to handle weekends and holidays.
    Matches the yfinance patterns used in main.py.
    """
    start = after_date + timedelta(days=1)
    end   = after_date + timedelta(days=7)

    try:
        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
    except Exception as e:
        print(f"  ⚠️  Price download failed for {ticker}: {e}")
        return None

    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return float(df["Open"].iloc[0])


def get_current_open(ticker: str) -> float | None:
    """
    Fetch today's open price for exit checks.
    Uses period='5d' to ensure we get the most recent trading day.
    """
    try:
        df = yf.download(
            ticker,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
    except Exception as e:
        print(f"  ⚠️  Price download failed for {ticker}: {e}")
        return None

    if df is None or df.empty:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return float(df["Open"].iloc[-1])


def get_trading_days_held(entry_date: date, today: date) -> int:
    """
    Count trading days between entry_date and today (inclusive of today).
    Uses yfinance SPY calendar as a proxy for market open days.
    """
    try:
        df = yf.download(
            "SPY",
            start=entry_date.isoformat(),
            end=(today + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if df is None or df.empty:
            # Fallback: rough calendar day estimate
            return (today - entry_date).days
        return len(df)
    except Exception:
        return (today - entry_date).days


# ── Exit checker ───────────────────────────────────────────────────────────────

def check_paper_exits(supabase, today: date):
    """
    Check all open paper trades for stop / target / time exits.
    Uses today's open price as the exit price (matches existing strategy logic).
    Run this BEFORE fill_paper_slots so freed slots are available immediately.
    """
    print("\n=== PAPER TRADING: CHECKING EXITS ===")

    for config, cfg in CONFIGS.items():
        open_trades = get_open_trades(supabase, config)

        if not open_trades:
            print(f"  {config}: no open trades")
            continue

        print(f"  {config}: checking {len(open_trades)} open trade(s)")

        for trade in open_trades:
            ticker     = trade["ticker"]
            entry      = float(trade["entry_price"])
            stop       = float(trade["stop_price"])
            target     = float(trade["target_price"])
            shares     = float(trade["shares"])
            max_date   = date.fromisoformat(trade["max_exit_date"])
            entry_date = date.fromisoformat(trade["entry_date"])

            today_open = get_current_open(ticker)
            if today_open is None:
                print(f"    {ticker}: could not fetch price, skipping")
                continue

            exit_price  = None
            exit_reason = None

            # Priority: stop > target > time (conservative on same-day conflicts)
            if today_open <= stop:
                exit_price, exit_reason = stop, "stop"
            elif today_open >= target:
                exit_price, exit_reason = target, "target"
            elif today >= max_date:
                exit_price, exit_reason = today_open, "time"

            if exit_reason:
                days_held   = get_trading_days_held(entry_date, today)
                pnl_dollars = round(shares * (exit_price - entry), 2)
                pnl_pct     = round((exit_price - entry) / entry * 100, 4)

                try:
                    supabase.table("paper_trades").update({
                        "status":      "closed",
                        "exit_date":   today.isoformat(),
                        "exit_price":  exit_price,
                        "exit_reason": exit_reason,
                        "days_held":   days_held,
                        "pnl_pct":     pnl_pct,
                        "pnl_dollars": pnl_dollars,
                    }).eq("id", trade["id"]).execute()

                    print(
                        f"    ✓ {ticker} [{config}]: {exit_reason} exit"
                        f" @ ${exit_price:.2f} | P&L: {pnl_pct:+.2f}%"
                        f" (${pnl_dollars:+.2f}) | {days_held}d"
                    )
                except Exception as e:
                    print(f"    ❌ {ticker}: Supabase update failed — {e}")
            else:
                days_held = get_trading_days_held(entry_date, today)
                print(f"    {ticker}: still open ({days_held}d held)")


# ── Slot filler ────────────────────────────────────────────────────────────────

def fill_paper_slots(supabase, signals: pd.DataFrame, today: date):
    """
    Fill open slots with today's top-ranked HighMomentumSetup signals.

    signals: DataFrame already filtered (RS > 50) and sorted by
             relative_strength descending. Must have columns:
             ticker, relative_strength, rank

    Position sizing:
      - Both slots open:  position_size = available_cash / 2
      - One slot open:    position_size = all available_cash
      - No slots open:    log remaining signals as missed
    """
    print("\n=== PAPER TRADING: FILLING SLOTS ===")

    if signals.empty:
        print("  No signals today — nothing to fill")
        return

    for config, cfg in CONFIGS.items():
        open_trades     = get_open_trades(supabase, config)
        slots_open      = MAX_SLOTS - len(open_trades)
        already_held    = {t["ticker"] for t in open_trades}

        # Get account summary for position sizing
        summary         = get_account_summary(supabase, config)
        available_cash  = float(summary["available_cash"])

        print(f"\n  {config}: {slots_open} slot(s) open | available cash: ${available_cash:.2f}")

        if slots_open == 0:
            # Log all signals as missed
            candidates = [
                row for _, row in signals.iterrows()
                if row["ticker"] not in already_held
            ]
            for signal in candidates:
                _log_missed(supabase, config, signal, today)
            if candidates:
                print(f"    All {len(candidates)} signal(s) logged as missed (slots full)")
            continue

        # Filter out already-held tickers
        candidates = [
            row for _, row in signals.iterrows()
            if row["ticker"] not in already_held
        ]

        if not candidates:
            print(f"    No new candidates (all signals already held)")
            continue

        to_enter = candidates[:slots_open]
        to_miss  = candidates[slots_open:]

        # Calculate position size based on slots opening
        if slots_open == MAX_SLOTS:
            # Both slots open: split evenly
            position_size = round(available_cash / 2, 2)
        else:
            # One slot open: deploy all available cash
            position_size = round(available_cash, 2)

        for signal in to_enter:
            ticker = signal["ticker"]

            # Get next day's open as entry price
            entry_price = get_next_day_open(ticker, today)
            if entry_price is None:
                print(f"    ⚠️  {ticker}: could not fetch entry price, logging as missed")
                _log_missed(supabase, config, signal, today)
                continue

            stop_price   = round(entry_price * (1 - cfg["stop_pct"]),  4)
            target_price = round(entry_price * (1 + cfg["target_pct"]), 4)
            shares       = round(position_size / entry_price,           6)
            cost_basis   = round(shares * entry_price,                  2)
            entry_date   = _next_trading_day(today)
            max_exit     = _add_trading_days(entry_date, cfg["max_days"])

            trade_id = f"PT-{config[:3].upper()}-{ticker}-{today.isoformat()}"

            try:
                supabase.table("paper_trades").upsert({
                    "id":                 trade_id,
                    "config":             config,
                    "ticker":             ticker,
                    "signal_date":        today.isoformat(),
                    "entry_date":         entry_date.isoformat(),
                    "entry_price":        entry_price,
                    "stop_price":         stop_price,
                    "target_price":       target_price,
                    "max_exit_date":      max_exit.isoformat(),
                    "relative_strength":  _safe_float(signal.get("relative_strength")),
                    "rank":               _safe_int(signal.get("rank")),
                    "position_size":      position_size,
                    "shares":             shares,
                    "cost_basis":         cost_basis,
                    "status":             "open",
                }).execute()

                print(
                    f"    ✓ ENTER {ticker} [{config}]:"
                    f" ${entry_price:.2f} | stop ${stop_price:.2f}"
                    f" | target ${target_price:.2f}"
                    f" | {shares:.4f} shares @ ${position_size:.2f}"
                )
            except Exception as e:
                print(f"    ❌ {ticker}: Supabase insert failed — {e}")

        for signal in to_miss:
            _log_missed(supabase, config, signal, today)


# ── Missed signal logger ───────────────────────────────────────────────────────

def _log_missed(supabase, config: str, signal, today: date):
    """Log a signal that couldn't be taken due to full slots."""
    ticker   = signal["ticker"]
    trade_id = f"PT-{config[:3].upper()}-MISS-{ticker}-{today.isoformat()}"

    try:
        supabase.table("paper_trades").upsert({
            "id":                trade_id,
            "config":            config,
            "ticker":            ticker,
            "signal_date":       today.isoformat(),
            "status":            "missed",
            "relative_strength": _safe_float(signal.get("relative_strength")),
            "rank":              _safe_int(signal.get("rank")),
        }).execute()
        print(f"    — MISSED {ticker} [{config}] (logged)")
    except Exception as e:
        print(f"    ❌ {ticker}: failed to log missed — {e}")


# ── Date helpers ───────────────────────────────────────────────────────────────

def _next_trading_day(from_date: date) -> date:
    """Return the next weekday after from_date (Mon–Fri proxy for trading day)."""
    d = from_date + timedelta(days=1)
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d += timedelta(days=1)
    return d


def _add_trading_days(from_date: date, n: int) -> date:
    """Add n weekdays to from_date."""
    d = from_date
    added = 0
    while added < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


# ── Type safety helpers ────────────────────────────────────────────────────────

def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return None if np.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


# ── Public entrypoint ──────────────────────────────────────────────────────────

def run_paper_trading(highmom_signals: pd.DataFrame, supabase, today: date):
    """
    Main entrypoint called from main.py.

    highmom_signals: DataFrame of today's HighMomentumSetup signals,
                     already filtered for RS > 50 and ranked.
                     Expected columns: ticker, relative_strength, rank

    Order of operations:
      1. Check exits on all open paper trades (frees slots)
      2. Fill newly open slots with today's signals
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING — 52-WEEK HIGH MOMENTUM")
    print("=" * 60)

    # Step 1: exits first so freed slots are available this same run
    check_paper_exits(supabase, today)

    # Step 2: fill slots with today's signals
    fill_paper_slots(supabase, highmom_signals, today)

    print("\n" + "=" * 60)
    print("PAPER TRADING COMPLETE")
    print("=" * 60 + "\n")