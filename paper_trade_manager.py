"""
paper_trade_manager.py

Manages paper trading for the 52-Week High Momentum strategy.
Two independent accounts (conservative, aggressive), each starting at $1,000.
Max 2 simultaneous positions per account at $500 each (dynamic sizing).

Entry flow:
  Evening (6 PM): main.py logs new trades as 'pending' — no entry price yet
  Morning (9:45 AM): entry_price.py fetches real open, converts 'pending' → 'open'

Missed trades are tracked hypothetically — same exit logic, no dollar P&L.

Usage in main.py:
    entered, exited, open_trades = run_paper_trading(highmom_signals, supabase, today)
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta


# ── Config ─────────────────────────────────────────────────────────────────────

CONFIGS = {
    "conservative": {
        "stop_pct":   0.02,
        "target_pct": 0.07,
        "max_days":   10,
    },
    "aggressive": {
        "stop_pct":   0.02,
        "target_pct": 0.15,
        "max_days":   20,
    },
}

MAX_SLOTS       = 2
STARTING_EQUITY = 1000.00


# ── Supabase helpers ───────────────────────────────────────────────────────────

def get_open_trades(supabase, config: str) -> list[dict]:
    res = (
        supabase.table("paper_trades")
        .select("*")
        .eq("config", config)
        .eq("status", "open")
        .execute()
    )
    return res.data or []


def get_active_trades(supabase, config: str) -> list[dict]:
    """Open + pending both count toward slot usage."""
    res = (
        supabase.table("paper_trades")
        .select("*")
        .eq("config", config)
        .in_("status", ["open", "pending"])
        .execute()
    )
    return res.data or []


def get_all_open_trades(supabase) -> list[dict]:
    res = (
        supabase.table("paper_trades")
        .select("*")
        .eq("status", "open")
        .execute()
    )
    return res.data or []


def get_missed_trades_with_prices(supabase) -> list[dict]:
    """Fetch missed trades that have entry prices (ready for exit checking)."""
    res = (
        supabase.table("paper_trades")
        .select("*")
        .eq("status", "missed")
        .not_.is_("entry_price", "null")
        .is_("pnl_pct", "null")       # not yet resolved
        .execute()
    )
    return res.data or []


def get_account_summary(supabase, config: str) -> dict:
    res = (
        supabase.table("paper_account_summary")
        .select("*")
        .eq("config", config)
        .execute()
    )
    if res.data:
        return res.data[0]
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

def get_current_open(ticker: str) -> float | None:
    try:
        df = yf.download(
            ticker, period="5d", interval="1d",
            auto_adjust=False, progress=False,
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
    try:
        df = yf.download(
            "SPY",
            start=entry_date.isoformat(),
            end=(today + timedelta(days=1)).isoformat(),
            interval="1d", auto_adjust=False, progress=False,
        )
        if df is None or df.empty:
            return (today - entry_date).days
        return len(df)
    except Exception:
        return (today - entry_date).days


# ── Exit checker — real trades ─────────────────────────────────────────────────

def check_paper_exits(supabase, today: date) -> list[dict]:
    """
    Check all open paper trades for stop / target / time exits.
    Returns list of trades closed this run (for Discord alert).
    """
    print("\n=== PAPER TRADING: CHECKING EXITS ===")
    exited = []

    for config in CONFIGS:
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

                    exited.append({
                        "config":      config,
                        "ticker":      ticker,
                        "entry_price": entry,
                        "exit_price":  exit_price,
                        "exit_reason": exit_reason,
                        "pnl_pct":     pnl_pct,
                        "pnl_dollars": pnl_dollars,
                        "days_held":   days_held,
                    })

                except Exception as e:
                    print(f"    ❌ {ticker}: Supabase update failed — {e}")
            else:
                days_held = get_trading_days_held(entry_date, today)
                print(f"    {ticker}: still open ({days_held}d held)")

    return exited


# ── Exit checker — missed trades (hypothetical) ───────────────────────────────

def check_missed_exits(supabase, today: date):
    """
    Check hypothetical exits for missed trades that have entry prices.
    Stores pnl_pct only — no dollar amounts since these were never real.
    Status stays 'missed' — we just add exit fields for reference.
    """
    missed = get_missed_trades_with_prices(supabase)

    if not missed:
        return

    print(f"\n=== PAPER TRADING: CHECKING MISSED TRADE EXITS ({len(missed)}) ===")

    for trade in missed:
        ticker     = trade["ticker"]
        entry      = float(trade["entry_price"])
        stop       = float(trade["stop_price"])
        target     = float(trade["target_price"])
        max_date   = date.fromisoformat(trade["max_exit_date"])
        entry_date = date.fromisoformat(trade["entry_date"])
        config     = trade["config"]

        today_open = get_current_open(ticker)
        if today_open is None:
            print(f"    {ticker}: could not fetch price, skipping")
            continue

        exit_price  = None
        exit_reason = None

        if today_open <= stop:
            exit_price, exit_reason = stop, "stop"
        elif today_open >= target:
            exit_price, exit_reason = target, "target"
        elif today >= max_date:
            exit_price, exit_reason = today_open, "time"

        if exit_reason:
            days_held = get_trading_days_held(entry_date, today)
            pnl_pct   = round((exit_price - entry) / entry * 100, 4)

            try:
                supabase.table("paper_trades").update({
                    "exit_date":   today.isoformat(),
                    "exit_price":  exit_price,
                    "exit_reason": exit_reason,
                    "days_held":   days_held,
                    "pnl_pct":     pnl_pct,
                    # status stays 'missed', pnl_dollars stays null
                }).eq("id", trade["id"]).execute()

                print(
                    f"    📋 {ticker} [{config}] (hypothetical): {exit_reason}"
                    f" @ ${exit_price:.2f} | P&L: {pnl_pct:+.2f}% | {days_held}d"
                )
            except Exception as e:
                print(f"    ❌ {ticker}: Supabase update failed — {e}")
        else:
            days_held = get_trading_days_held(entry_date, today)
            print(f"    📋 {ticker} [{config}] (hypothetical): still open ({days_held}d)")


# ── Slot filler ────────────────────────────────────────────────────────────────

def fill_paper_slots(supabase, signals: pd.DataFrame, today: date) -> list[dict]:
    """
    Log today's top signals as 'pending'. entry_price.py activates them tomorrow.
    Returns list of pending trades for Discord alert.
    """
    print("\n=== PAPER TRADING: FILLING SLOTS ===")
    entered = []

    if signals.empty:
        print("  No signals today — nothing to fill")
        return entered

    for config, cfg in CONFIGS.items():
        active_trades  = get_active_trades(supabase, config)
        slots_open     = MAX_SLOTS - len(active_trades)
        already_held   = {t["ticker"] for t in active_trades}
        summary        = get_account_summary(supabase, config)
        available_cash = float(summary["available_cash"])

        print(f"\n  {config}: {slots_open} slot(s) open | available cash: ${available_cash:.2f}")

        if slots_open == 0:
            candidates = [r for _, r in signals.iterrows() if r["ticker"] not in already_held]
            for signal in candidates:
                _log_missed(supabase, config, signal, today)
            if candidates:
                print(f"    All {len(candidates)} signal(s) logged as missed (slots full)")
            continue

        candidates = [r for _, r in signals.iterrows() if r["ticker"] not in already_held]

        if not candidates:
            print(f"    No new candidates (all signals already held)")
            continue

        to_enter = candidates[:slots_open]
        to_miss  = candidates[slots_open:]

        position_size = round(available_cash / 2, 2) if slots_open == MAX_SLOTS else round(available_cash, 2)

        for signal in to_enter:
            ticker   = signal["ticker"]
            trade_id = f"PT-{config[:3].upper()}-{ticker}-{today.isoformat()}"

            try:
                supabase.table("paper_trades").upsert({
                    "id":                trade_id,
                    "config":            config,
                    "ticker":            ticker,
                    "signal_date":       today.isoformat(),
                    "status":            "pending",
                    "position_size":     position_size,
                    "relative_strength": _safe_float(signal.get("relative_strength")),
                    "rank":              _safe_int(signal.get("rank")),
                }).execute()

                print(
                    f"    ⏳ PENDING {ticker} [{config}]: "
                    f"${position_size:.2f} allocated | "
                    f"RS: {_safe_float(signal.get('relative_strength')):.1f} | "
                    f"entry price fetched tomorrow at open"
                )

                entered.append({
                    "config":            config,
                    "ticker":            ticker,
                    "position_size":     position_size,
                    "relative_strength": _safe_float(signal.get("relative_strength")),
                })

            except Exception as e:
                print(f"    ❌ {ticker}: Supabase insert failed — {e}")

        for signal in to_miss:
            _log_missed(supabase, config, signal, today)

    return entered


# ── Missed signal logger ───────────────────────────────────────────────────────

def _log_missed(supabase, config: str, signal, today: date):
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
    d = from_date + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _add_trading_days(from_date: date, n: int) -> date:
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
    Returns (entered, exited, open_trades) for Discord alert.
    """
    print("\n" + "=" * 60)
    print("PAPER TRADING — 52-WEEK HIGH MOMENTUM")
    print("=" * 60)

    exited      = check_paper_exits(supabase, today)
    check_missed_exits(supabase, today)          # hypothetical — no return value needed
    entered     = fill_paper_slots(supabase, highmom_signals, today)
    open_trades = get_all_open_trades(supabase)

    print("\n" + "=" * 60)
    print("PAPER TRADING COMPLETE")
    print("=" * 60 + "\n")

    return entered, exited, open_trades