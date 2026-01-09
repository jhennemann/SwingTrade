import os
import pandas as pd
import matplotlib.pyplot as plt


class ChartGenerator:
    def __init__(self, output_dir="data/charts"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def save_chart(
        self,
        df: pd.DataFrame,
        ticker: str,
        signal_date: pd.Timestamp,
        lookback_days: int = 180
    ):
        """
        Saves a price + SMA + volume chart highlighting the signal date.
        """

        # Focus on recent window
        df = df.copy()
        df = df.loc[df.index <= signal_date].tail(lookback_days)

        fig, (ax_price, ax_vol) = plt.subplots(
            2,
            1,
            figsize=(10, 6),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]}
        )

        # ---- Price + MAs ----
        ax_price.plot(df.index, df["Close"], label="Close", linewidth=1.5)
        ax_price.plot(df.index, df["SMA20"], label="SMA20", linestyle="--")
        ax_price.plot(df.index, df["SMA50"], label="SMA50", linestyle="--")

        ax_price.axvline(signal_date, color="red", linestyle=":", label="Signal")

        ax_price.set_title(f"{ticker} — Pullback Setup")
        ax_price.legend(loc="upper left")
        ax_price.grid(True)

        # ---- Volume ----
        ax_vol.bar(df.index, df["Volume"], width=1.0)
        ax_vol.set_ylabel("Volume")
        ax_vol.grid(True)

        plt.tight_layout()

        # Save file
        filename = f"{ticker}_{signal_date.date().isoformat()}.png"
        path = os.path.join(self.output_dir, filename)
        plt.savefig(path)
        plt.close(fig)

        return path
