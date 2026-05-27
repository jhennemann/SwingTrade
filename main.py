from src.universe import SP500UniverseStockAnalysis, Nasdaq100Universe
from src.setup_rules import PullbackUptrendSetup, HighMomentumSetup
from src.scanner import SetupScanner
from src.charting import ChartGenerator
from src.reporting import PDFGalleryExporter

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, date

from src.ranking import rank_signals
from src.market_calendar import market_is_open

import os
from supabase import create_client

from paper_trade_manager import run_paper_trading


# ── Constants ──────────────────────────────────────────────────────────────────
STOP_PCT    = 0.98
TARGET_PCT  = 1.07
MAX_DAYS    = 10

# ── Discord ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")


def send_discord(message: str):
    """Send a chunked message to Discord."""
    if not DISCORD_WEBHOOK:
        print("No DISCORD_WEBHOOK_URL set — skipping Discord alert")
        return
    chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
    try:
        for chunk in chunks:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": chunk},
                timeout=10,
            ).raise_for_status()
        print("✅ Alert sent to Discord")
    except Exception as e:
        print(f"❌ Failed to send Discord alert: {e}")


def send_paper_trading_alert(
    entered: list[dict],
    exited: list[dict],
    open_trades: list[dict],
    run_date: date,
):
    """Send a Discord alert summarizing paper trading activity for the day."""
    if not DISCORD_WEBHOOK:
        print("No DISCORD_WEBHOOK_URL set — skipping paper trading alert")
        return

    lines = [
        f"📈 **Paper Trading Update — {run_date.isoformat()}**",
        f"*52-Week High Momentum · 2 accounts · $1,000 each*",
        "",
    ]

    # ── Exits ──────────────────────────────────────────────────────────────────
    if exited:
        lines.append("**— Closed Today —**")
        for t in exited:
            cfg_label   = "CON" if t["config"] == "conservative" else "AGG"
            pnl_pct     = float(t.get("pnl_pct") or 0)
            pnl_dollars = float(t.get("pnl_dollars") or 0)

            if t["exit_reason"] == "target":
                emoji = "🎯"
            elif t["exit_reason"] == "stop":
                emoji = "🛑"
            else:
                emoji = "⏱️"

            lines.append(
                f"{emoji} **{t['ticker']}** [{cfg_label}] — {t['exit_reason'].upper()}\n"
                f"   Entry: ${float(t['entry_price']):.2f} | Exit: ${float(t['exit_price']):.2f} | "
                f"P&L: {pnl_pct:+.2f}% (${pnl_dollars:+.2f}) | Day {t['days_held']}"
            )
        lines.append("")

    # ── Entries ────────────────────────────────────────────────────────────────
    if entered:
        lines.append("**— Entering Tomorrow at Open —**")
        for t in entered:
            cfg_label = "CON" if t["config"] == "conservative" else "AGG"
            rs        = float(t.get("relative_strength") or 0)
            lines.append(
                f"⏳ **{t['ticker']}** [{cfg_label}]\n"
                f"   RS: {rs:.1f} | Size: ${float(t['position_size']):.2f} | "
                f"Entry price fetched tomorrow at open"
            )
        lines.append("")

    # ── Open positions ─────────────────────────────────────────────────────────
    if open_trades:
        lines.append("**— Open Positions —**")
        for t in open_trades:
            cfg_label = "CON" if t["config"] == "conservative" else "AGG"
            days      = (run_date - date.fromisoformat(t["entry_date"])).days
            max_days  = 10 if t["config"] == "conservative" else 20
            rs        = float(t.get("relative_strength") or 0)
            lines.append(
                f"📊 **{t['ticker']}** [{cfg_label}] | RS: {rs:.1f} | "
                f"Entry: ${float(t['entry_price']):.2f} | "
                f"Stop: ${float(t['stop_price']):.2f} | "
                f"Target: ${float(t['target_price']):.2f} | "
                f"Day {days}/{max_days}"
            )
        lines.append("")

    if not exited and not entered and not open_trades:
        lines.append("No activity today — no open positions, no signals.")

    send_discord("\n".join(lines))


# ── Exit logic (pullback strategy) ─────────────────────────────────────────────

def check_exits(supabase):
    response = supabase.table("signals").select("*").eq("status", "open").execute()
    open_signals = response.data

    if not open_signals:
        print("No open signals to check for exits.")
        return

    print(f"\n=== CHECKING EXITS FOR {len(open_signals)} OPEN SIGNALS ===")

    for signal in open_signals:
        ticker    = signal["ticker"]
        buy_price = signal["buy_price"]
        last_date = signal["last_date"]

        if not buy_price or not last_date:
            print(f"  {ticker}: missing buy_price or last_date, skipping")
            continue

        stop_price   = round(buy_price * STOP_PCT, 4)
        target_price = round(buy_price * TARGET_PCT, 4)

        try:
            df = yf.download(
                ticker,
                start=last_date,
                end=date.today().isoformat(),
                interval="1d",
                auto_adjust=False,
                progress=False
            )
        except Exception as e:
            print(f"  {ticker}: download failed — {e}")
            continue

        if df is None or df.empty:
            print(f"  {ticker}: no price data returned")
            continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.iloc[1:].copy()

        if df.empty:
            print(f"  {ticker}: no post-entry price data yet")
            continue

        exit_price  = None
        exit_date   = None
        exit_reason = None
        days_held   = None

        for i, (idx, row) in enumerate(df.iterrows(), start=1):
            day_high  = float(row["High"])
            day_low   = float(row["Low"])
            day_close = float(row["Close"])
            day_date  = idx.date() if hasattr(idx, 'date') else idx

            hit_stop   = day_low <= stop_price
            hit_target = day_high >= target_price
            hit_time   = i >= MAX_DAYS

            if hit_stop and hit_target:
                exit_price, exit_date, exit_reason, days_held = stop_price, day_date, "stop", i
                break
            elif hit_stop:
                exit_price, exit_date, exit_reason, days_held = stop_price, day_date, "stop", i
                break
            elif hit_target:
                exit_price, exit_date, exit_reason, days_held = target_price, day_date, "target", i
                break
            elif hit_time:
                exit_price, exit_date, exit_reason, days_held = day_close, day_date, "time", i
                break

        if exit_price is not None:
            win_loss = round((exit_price - buy_price) / buy_price, 4)
            try:
                supabase.table("signals").update({
                    "status":      "closed",
                    "exit_price":  exit_price,
                    "exit_date":   exit_date.isoformat(),
                    "exit_reason": exit_reason,
                    "win_loss":    win_loss,
                    "days_held":   days_held,
                }).eq("id", signal["id"]).execute()
                print(f"  ✓ {ticker}: {exit_reason} exit on {exit_date} | P&L: {win_loss*100:.2f}% | days: {days_held}")
            except Exception as e:
                print(f"  ❌ {ticker}: failed to update Supabase — {e}")
        else:
            print(f"  {ticker}: still open ({len(df)} days in trade)")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not market_is_open():
        print("Market is closed today. Skipping scan.")
        return

    # ── Load universes ─────────────────────────────────────────────────────────
    print("Loading stock universes...")
    sp500 = SP500UniverseStockAnalysis()
    print(f"✓ S&P 500: {len(sp500.tickers)} stocks")

    nasdaq100 = Nasdaq100Universe()
    print(f"✓ NASDAQ 100: {len(nasdaq100.tickers)} stocks")

    all_tickers = list(set(sp500.tickers + nasdaq100.tickers))
    overlap = len(sp500.tickers) + len(nasdaq100.tickers) - len(all_tickers)
    print(f"✓ Combined universe: {len(all_tickers)} stocks ({overlap} overlap)")
    print()

    # ── Pullback Uptrend scan ──────────────────────────────────────────────────
    setup = PullbackUptrendSetup(pullback_pct=0.02, use_volume=True)
    scanner = SetupScanner(setup=setup, lookback="2y", require_market_ok=True)
    market_ok, spy_date, spy_close, spy_sma200 = scanner.market_ok()
    results = scanner.scan(all_tickers)
    today = results[results["has_signal_today"]].copy() if not results.empty else pd.DataFrame()

    if not today.empty:
        today = rank_signals(today)
        results = results.set_index('ticker')
        today_indexed = today.set_index('ticker')
        results.update(today_indexed)
        results = results.reset_index()

    print("\n=== PULLBACK SIGNALS TODAY ===")
    if not today.empty:
        display_cols = [c for c in ["rank", "ticker", "relative_strength", "last_date"] if c in today.columns]
        print(today[display_cols].to_string(index=False))
    else:
        print("No signals today.")

    # ── High Momentum scan ─────────────────────────────────────────────────────
    highmom_setup   = HighMomentumSetup(near_high_pct=0.02, volume_ratio_min=1.75)
    highmom_scanner = SetupScanner(setup=highmom_setup, lookback="2y", require_market_ok=True)
    highmom_results = highmom_scanner.scan(all_tickers)
    highmom_today   = (
        highmom_results[highmom_results["has_signal_today"]].copy()
        if not highmom_results.empty else pd.DataFrame()
    )

    if not highmom_today.empty:
        highmom_today = rank_signals(highmom_today)
        highmom_today = highmom_today[highmom_today["relative_strength"] > 50].copy()
        highmom_today = highmom_today.sort_values("relative_strength", ascending=False).reset_index(drop=True)
        print(f"\n=== HIGH MOMENTUM SIGNALS (RS > 50): {len(highmom_today)} ===")
        display_cols = [c for c in ["rank", "ticker", "relative_strength", "last_date"] if c in highmom_today.columns]
        print(highmom_today[display_cols].to_string(index=False))
    else:
        print("\n=== HIGH MOMENTUM SIGNALS: none today ===")

    # ── Run date ───────────────────────────────────────────────────────────────
    run_date = date.today()

    # ── Charts ─────────────────────────────────────────────────────────────────
    chart_gen = ChartGenerator(base_dir="data/charts")
    chart_paths = []

    for _, row in today.iterrows():
        ticker = row["ticker"]
        signal_date = pd.to_datetime(row["most_recent_signal_date"])
        df = yf.download(ticker, period="1y", interval="1d", auto_adjust=False, progress=False)
        if df is None or df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = setup.prepare(df)
        chart_path = chart_gen.save_chart(
            df=df, ticker=ticker, signal_date=signal_date,
            run_date=run_date, filename="pullback_setup.png"
        )
        chart_paths.append(chart_path)
        print(f"Saved chart: {chart_path}")

    # ── PDF gallery ────────────────────────────────────────────────────────────
    if chart_paths:
        pdf_out = (
            f"data/charts/{run_date.year:04d}/{run_date.month:02d}/"
            f"{run_date.isoformat()}/gallery_{run_date.isoformat()}.pdf"
        )
        exporter = PDFGalleryExporter(cols=2, rows=2)
        pdf_path = exporter.export(
            image_paths=chart_paths,
            output_pdf_path=pdf_out,
            title="SwingTrade Setup Gallery - S&P 500 + NASDAQ 100",
            subtitle=(
                f"Signal date: {run_date.isoformat()} | "
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                f"Universe: {len(all_tickers)} stocks"
            ),
        )
        print(f"\nSaved PDF gallery: {pdf_path}")
    else:
        print("\nNo charts generated; skipping PDF export.")

    # ── CSV ────────────────────────────────────────────────────────────────────
    csv_path = (
        f"data/charts/{run_date.year:04d}/{run_date.month:02d}/"
        f"{run_date.isoformat()}/scan_results_{run_date.isoformat()}.csv"
    )
    if not today.empty:
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        today.to_csv(csv_path, index=False)
        print(f"\nSaved signals with RS: {csv_path}")
    else:
        print(f"\nNo signals today - skipping CSV save")

    # ── Supabase ───────────────────────────────────────────────────────────────
    supabase_url         = os.environ.get("SUPABASE_URL")
    supabase_service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    entered, exited, open_trades = [], [], []

    if supabase_url and supabase_service_key:
        try:
            supabase = create_client(supabase_url, supabase_service_key)

            # 1. Check exits for open pullback signals
            check_exits(supabase)

            # 2. Push today's pullback signals
            if not today.empty:
                supabase.table("signals").delete().eq("last_date", run_date.isoformat()).execute()
                records = today.to_dict(orient="records")
                for record in records:
                    for k, v in record.items():
                        if isinstance(v, float) and np.isnan(v):
                            record[k] = None
                        elif hasattr(v, 'isoformat'):
                            record[k] = v.isoformat()
                    record["status"] = "open"
                supabase.table("signals").insert(records).execute()
                print(f"\n✓ Pushed {len(records)} new pullback signals to Supabase")
            else:
                print("\nNo new pullback signals to push to Supabase")

            # 3. Paper trading — exits first, then fill slots
            entered, exited, open_trades = run_paper_trading(highmom_today, supabase, run_date)

        except Exception as e:
            print(f"❌ Supabase error: {e}")
    else:
        print("Supabase credentials not found, skipping")

    # ── Discord alerts ─────────────────────────────────────────────────────────
    send_paper_trading_alert(entered, exited, open_trades, run_date)


if __name__ == "__main__":
    main()