import pandas as pd

class PullbackUptrendSetup:
    """
    Setup checks: Uptrend AND pullback yesterday AND reclaim today
      - Trend: Close > SMA50 and SMA20 > SMA50
      - Pullback: Yesterday was near SMA20 (within pullback_pct) and at/below SMA20
      - Confirmation: Today closes back above SMA20 (reclaim)
      - Optional: Pullback day volume < VOL_SMA20 (quiet pullback)
    """
    def __init__(self, pullback_pct: float = 0.02, use_volume: bool = True):
        self.pullback_pct = pullback_pct
        self.use_volume = use_volume

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Close"] = df["Close"].astype(float)
        df["Volume"] = df["Volume"].astype(float)

        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
        return df

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # --- Trend filter (today) ---
        trend = (df["Close"] > df["SMA50"]) & (df["SMA20"] > df["SMA50"])

        # --- Pullback & reclaim logic uses yesterday vs today ---
        prev_close = df["Close"].shift(1)
        prev_sma20 = df["SMA20"].shift(1)

        # Yesterday was close to SMA20 (within pullback_pct) and at/below SMA20
        pullback_near = ((prev_close - prev_sma20).abs() / prev_sma20) <= self.pullback_pct
        pullback_below_or_at = prev_close <= prev_sma20
        pullback_day = pullback_near & pullback_below_or_at

        # Today reclaims SMA20 (closes above)
        reclaim = df["Close"] > df["SMA20"]

        # Combine
        signal = trend & pullback_day & reclaim

        # Optional: quiet pullback volume on the pullback day (yesterday)
        if self.use_volume:
            prev_vol = df["Volume"].shift(1)
            prev_vol_sma20 = df["VOL_SMA20"].shift(1)
            quiet_pullback = prev_vol < prev_vol_sma20
            signal = signal & quiet_pullback

        df["signal"] = signal.fillna(False)
        return df
