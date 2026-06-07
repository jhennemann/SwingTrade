import pandas as pd

class PullbackUptrendSetup:
    """
    Setup checks: Uptrend AND pullback yesterday AND reclaim today
      - Trend: Close > SMA50 and SMA20 > SMA50
      - Pullback: Yesterday was near SMA20 (within pullback_pct) and at/below SMA20
      - Confirmation: Today closes back above SMA20 by reclaim_pct
      - Optional: Pullback day volume < VOL_SMA20 (quiet pullback)
      - Optional: Close > SMA200 for longer-term trend confirmation
      - Optional: RSI was below rsi_oversold on pullback day (yesterday)
      - Optional: RSI recovered above rsi_recover on signal day (today)
    """
    def __init__(
        self,
        pullback_pct: float = 0.02,
        use_volume: bool = True,
        reclaim_pct: float = 0.0,
        require_sma200: bool = False,
        use_rsi: bool = False,
        rsi_period: int = 14,
        rsi_oversold: float = 40.0,
        rsi_recover: float = 40.0,
    ):
        self.pullback_pct = pullback_pct
        self.use_volume = use_volume
        self.reclaim_pct = reclaim_pct
        self.require_sma200 = require_sma200
        self.use_rsi = use_rsi
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_recover = rsi_recover

    def _compute_rsi(self, close: pd.Series, period: int) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        return 100 - (100 / (1 + rs))

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["Close"] = df["Close"].astype(float)
        df["Volume"] = df["Volume"].astype(float)

        df["SMA20"] = df["Close"].rolling(20).mean()
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean()

        if self.use_rsi:
            df["RSI"] = self._compute_rsi(df["Close"], self.rsi_period)

        return df

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # --- Trend filter (today) ---
        trend = (df["Close"] > df["SMA50"]) & (df["SMA20"] > df["SMA50"])
        if self.require_sma200:
            trend = trend & (df["Close"] > df["SMA200"])

        # --- Pullback & reclaim logic ---
        prev_close = df["Close"].shift(1)
        prev_sma20 = df["SMA20"].shift(1)
        prev2_close = df["Close"].shift(2)
        prev2_sma20 = df["SMA20"].shift(2)

        # Two days ago was the pullback day (near and below SMA20)
        pullback_near = ((prev2_close - prev2_sma20).abs() / prev2_sma20) <= self.pullback_pct
        pullback_below_or_at = prev2_close <= prev2_sma20
        pullback_day = pullback_near & pullback_below_or_at

        # Yesterday AND today both close above SMA20 (two consecutive reclaims)
        reclaim_yesterday = prev_close > (prev_sma20 * (1 + self.reclaim_pct))
        reclaim_today = df["Close"] > (df["SMA20"] * (1 + self.reclaim_pct))
        reclaim = reclaim_yesterday & reclaim_today

        # Combine
        signal = trend & pullback_day & reclaim

        # Optional: quiet pullback volume on the pullback day (two days ago)
        if self.use_volume:
            prev2_vol = df["Volume"].shift(2)
            prev2_vol_sma20 = df["VOL_SMA20"].shift(2)
            quiet_pullback = prev2_vol < prev2_vol_sma20
            signal = signal & quiet_pullback

        # Optional: RSI was oversold on pullback day AND recovered today
        if self.use_rsi:
            prev2_rsi = df["RSI"].shift(2)
            rsi_was_oversold = prev2_rsi < self.rsi_oversold
            rsi_recovered = df["RSI"] > self.rsi_recover
            signal = signal & rsi_was_oversold & rsi_recovered

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
    
class HighMomentumSetup:
    """
    52-week high momentum setup.
    
    Signal: Stock closes at or near a new 52-week high on above average volume.
      - Price: Close within near_high_pct of 52-week high
      - Volume: Above average (volume_ratio_min x VOL_SMA20)
      - Trend: Close > SMA50 and SMA200
    """
    def __init__(
        self,
        near_high_pct: float = 0.02,
        volume_ratio_min: float = 1.5,
        lookback_days: int = 252,
    ):
        self.near_high_pct = near_high_pct
        self.volume_ratio_min = volume_ratio_min
        self.lookback_days = lookback_days

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = df[col].astype(float)

        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        df["VOL_SMA20"] = df["Volume"].rolling(20).mean().shift(1)
        df["volume_ratio"] = df["Volume"] / df["VOL_SMA20"]
        df["high_52w"] = df["Close"].rolling(self.lookback_days).max().shift(1)

        return df

    def apply(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        uptrend = (df["Close"] > df["SMA50"]) & (df["Close"] > df["SMA200"])

        if self.near_high_pct == 0.0:
            near_high = df["Close"] > df["high_52w"]  # strict new high
        else:
            near_high = df["Close"] >= df["high_52w"] * (1 - self.near_high_pct)

        volume_ok = df["volume_ratio"] >= self.volume_ratio_min

        signal = uptrend & near_high & volume_ok
        df["signal"] = signal.fillna(False)
        return df