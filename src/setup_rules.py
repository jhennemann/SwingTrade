import pandas as pd

class PullbackUptrendSetup:
    """
    Setup checks: Uptrend AND pullback yesterday AND reclaim today
      - Trend: Close > SMA50 and SMA20 > SMA50
      - Pullback: Yesterday was near SMA20 (within pullback_pct) and at/below SMA20
      - Confirmation: Today closes back above SMA20 by reclaim_pct
      - Optional: Pullback day volume < VOL_SMA20 (quiet pullback)
      - Optional: Close > SMA200 for longer-term trend confirmation
    """
    def __init__(
        self,
        pullback_pct: float = 0.02,
        use_volume: bool = True,
        reclaim_pct: float = 0.0,
        require_sma200: bool = False,
    ):
        self.pullback_pct = pullback_pct
        self.use_volume = use_volume
        self.reclaim_pct = reclaim_pct
        self.require_sma200 = require_sma200

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Close"] = df["Close"].astype(float)
        df["Volume"] = df["Volume"].astype(float)

        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
        return df

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # --- Trend filter (today) ---
        trend = (df["Close"] > df["SMA50"]) & (df["SMA20"] > df["SMA50"])
        if self.require_sma200:
            trend = trend & (df["Close"] > df["SMA200"])

        # --- Pullback & reclaim logic uses yesterday vs today ---
        prev_close = df["Close"].shift(1)
        prev_sma20 = df["SMA20"].shift(1)

        # Yesterday was close to SMA20 (within pullback_pct) and at/below SMA20
        pullback_near = ((prev_close - prev_sma20).abs() / prev_sma20) <= self.pullback_pct
        pullback_below_or_at = prev_close <= prev_sma20
        pullback_day = pullback_near & pullback_below_or_at

        # Today reclaims SMA20 by the configured margin
        reclaim = df["Close"] > (df["SMA20"] * (1 + self.reclaim_pct))

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


class BreakoutSetup:
    """
    Price breakout setup.

    The base/consolidation range is calculated from prior trading days only, so
    the current day's breakout or near-resistance close is not allowed to define
    its own resistance level.
    """
    def __init__(
        self,
        min_base_days: int = 15,
        max_base_days: int = 30,
        max_range_pct: float = 0.05,
        near_resistance_pct: float = 0.03,
        volume_ratio_min: float = 1.5,
        breakout_buffer_pct: float = 0.0,
        breakout_only: bool = False,
    ):
        self.min_base_days = min_base_days
        self.max_base_days = max_base_days
        self.max_range_pct = max_range_pct
        self.near_resistance_pct = near_resistance_pct
        self.volume_ratio_min = volume_ratio_min
        self.breakout_buffer_pct = breakout_buffer_pct
        self.breakout_only = breakout_only

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = df[col].astype(float)

        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean().shift(1)
        df["volume_ratio"] = df["Volume"] / df["VOL_SMA20"]

        df["consolidation_length"] = float("nan")
        df["resistance_level"] = float("nan")
        df["base_low"] = float("nan")
        df["base_range_pct"] = float("nan")

        for length in range(self.min_base_days, self.max_base_days + 1):
            resistance = df["High"].rolling(length).max().shift(1)
            base_low = df["Low"].rolling(length).min().shift(1)
            range_pct = (resistance - base_low) / base_low
            valid_base = range_pct <= self.max_range_pct

            df.loc[valid_base, "consolidation_length"] = length
            df.loc[valid_base, "resistance_level"] = resistance[valid_base]
            df.loc[valid_base, "base_low"] = base_low[valid_base]
            df.loc[valid_base, "base_range_pct"] = range_pct[valid_base]

        df["base_height"] = df["resistance_level"] - df["base_low"]
        return df

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        has_base = df["consolidation_length"].notna()
        uptrend = (df["Close"] > df["SMA50"]) & (df["Close"] > df["SMA200"])
        volume_ok = df["volume_ratio"] >= self.volume_ratio_min

        near_resistance = (
            df["Close"] >= df["resistance_level"] * (1 - self.near_resistance_pct)
        )
        breakout = (
            df["Close"] > df["resistance_level"] * (1 + self.breakout_buffer_pct)
        )

        price_ok = breakout if self.breakout_only else near_resistance
        signal = has_base & uptrend & price_ok & volume_ok

        df["breakout"] = breakout.fillna(False)
        df["signal"] = signal.fillna(False)
        return df
