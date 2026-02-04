import pandas as pd
import yfinance as yf

class SetupScanner:
    def __init__(self, setup, lookback: str = "2y", require_market_ok: bool = True):
        self.setup = setup
        self.lookback = lookback
        self.require_market_ok = require_market_ok

    def _download(self, ticker: str) -> pd.DataFrame:
        df = yf.download(
            ticker,
            period=self.lookback,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="column",
            threads=False,
        )

        if df is None or df.empty:
            return pd.DataFrame()

        # Flatten MultiIndex if it appears
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        expected = ["Open", "High", "Low", "Close", "Volume"]
        if any(c not in df.columns for c in expected):
            return pd.DataFrame()

        df = df[expected].dropna()
        return df

    def market_ok(self) -> tuple[bool, str, float, float]:
        """
        Returns:
          (ok, last_date_iso, spy_close, spy_sma200)
        ok is True if SPY Close > SMA200 on most recent trading day in lookback.
        """
        spy = self._download("SPY")
        if spy.empty or "Close" not in spy or spy["Close"].isna().all():
            print("SPY data missing — treating market as neutral")
            return (True, None, None, None)

        spy = spy.copy()
        spy["SMA200"] = spy["Close"].rolling(200).mean()

        last = spy.iloc[-1]
        last_date = spy.index[-1].date().isoformat()

        spy_close = float(last["Close"])
        spy_sma200 = float(last["SMA200"])

        ok = pd.notna(spy_sma200) and (spy_close > spy_sma200)
        return (bool(ok), last_date, spy_close, spy_sma200)

    def scan(self, tickers: list[str], max_tickers: int | None = None) -> pd.DataFrame:
        # Market filter (SPY > SMA200)
        if self.require_market_ok:
            ok, d, c, sma = self.market_ok()
            if not ok:
                msg = f"Market filter failed (SPY <= SMA200). Last date: {d}, Close: {c}, SMA200: {sma}"
                print(msg)
                return pd.DataFrame(columns=[
                    "ticker", "has_signal_today", "last_date", "most_recent_signal_date", "signals_in_lookback"
                ])
            print(f"Market filter passed: SPY > SMA200 on {d} (Close={c:.2f}, SMA200={sma:.2f})")

        tickers_to_scan = tickers[:max_tickers] if max_tickers else tickers
        rows = []

        for idx, t in enumerate(tickers_to_scan, start=1):
            df = self._download(t)
            if df.empty or len(df) < 60:
                continue

            df = self.setup.prepare(df)
            df = self.setup.apply(df)

            last_date = df.index[-1]
            has_signal_today = bool(df.iloc[-1]["signal"])

            sig_dates = df.index[df["signal"]].tolist()
            most_recent_signal = sig_dates[-1] if sig_dates else None

            rows.append({
                "ticker": t,
                "has_signal_today": has_signal_today,
                "last_date": last_date.date().isoformat(),
                "most_recent_signal_date": most_recent_signal.date().isoformat() if most_recent_signal else None,
                "signals_in_lookback": int(df["signal"].sum()),
            })

            if idx % 100 == 0:
                print(f"Scanned {idx}/{len(tickers_to_scan)} tickers...")

        out = pd.DataFrame(rows)
        if out.empty:
            return out

        out = out.sort_values(
            by=["has_signal_today", "signals_in_lookback"],
            ascending=[False, False]
        ).reset_index(drop=True)

        return out
