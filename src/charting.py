import os
from datetime import date
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date



class ChartGenerator:
    """
    Saves charts using the same date-partitioning format as progress,
    but under a separate root:

      data/charts/YYYY/MM/DD/TICKER/
    """

    def __init__(self, base_dir: str = "data/charts"):
        self.base_dir = base_dir

    def _run_dir(self, run_date: date, ticker: str) -> str:
        safe_ticker = ticker.replace("/", "-")
        date_folder = run_date.isoformat()  # YYYY-MM-DD

        return os.path.join(
            self.base_dir,
            f"{run_date.year:04d}",
            f"{run_date.month:02d}",
            date_folder,
            safe_ticker,
        )

    def save_chart(
        self,
        df: pd.DataFrame,
        ticker: str,
        signal_date: pd.Timestamp,
        lookback_days: int = 180,
        run_date: date | None = None,
        filename: str = "pullback_setup.png",
    ) -> str:
        """
        Saves a price + SMA + volume chart highlighting the signal date.

        Output:
          data/charts/YYYY/MM/DD/TICKER/<filename>
        """
        run_date = run_date or date.today()
        out_dir = self._run_dir(run_date, ticker)
        os.makedirs(out_dir, exist_ok=True)

        df = df.copy()
        df = df.loc[df.index <= signal_date].tail(lookback_days)

        if df.empty:
            raise ValueError(f"No data to plot for {ticker} at/before {signal_date}")

        fig, (ax_price, ax_vol) = plt.subplots(
            2,
            1,
            figsize=(10, 6),
            sharex=True,
            gridspec_kw={"height_ratios": [3, 1]},
        )

        # ---- Price + MAs ----
        ax_price.plot(df.index, df["Close"], label="Close", linewidth=1.5)
        ax_price.plot(df.index, df["SMA20"], label="SMA20", linestyle="--")
        ax_price.plot(df.index, df["SMA50"], label="SMA50", linestyle="--")

        ax_price.axvline(signal_date, color="red", linestyle=":", linewidth=1.5, label="Signal")

        ax_price.set_title(f"{ticker} — Pullback Setup")
        ax_price.legend(loc="upper left")
        ax_price.grid(True)

        # ---- Volume ----
        ax_vol.bar(df.index, df["Volume"], width=1.0)
        ax_vol.axvline(signal_date, color="red", linestyle=":", linewidth=1.0)
        ax_vol.set_ylabel("Volume")
        ax_vol.grid(True)

        plt.tight_layout()

        path = os.path.join(out_dir, filename)
        plt.savefig(path, dpi=150)
        plt.close(fig)

        return path
