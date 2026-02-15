import yfinance as yf
import pandas as pd


def calculate_relative_strength(ticker: str, lookback_days: int = 60) -> float:
    """
    Calculate how stock performed vs SPY over last 60 days.
    Higher = stronger momentum
    """
    try:
        stock = yf.download(ticker, period="3mo", progress=False, auto_adjust=False)
        spy = yf.download("SPY", period="3mo", progress=False, auto_adjust=False)
        
        if stock.empty or spy.empty or len(stock) < lookback_days:
            return 0.0
        
        # Flatten MultiIndex
        if isinstance(stock.columns, pd.MultiIndex):
            stock.columns = stock.columns.get_level_values(0)
        if isinstance(spy.columns, pd.MultiIndex):
            spy.columns = spy.columns.get_level_values(0)
        
        # Calculate returns
        stock_return = (stock["Close"].iloc[-1] / stock["Close"].iloc[-lookback_days]) - 1
        spy_return = (spy["Close"].iloc[-1] / spy["Close"].iloc[-lookback_days]) - 1
        
        # Relative strength = outperformance vs market
        return float((stock_return - spy_return) * 100)  # As percentage
        
    except Exception as e:
        print(f"⚠️  RS calculation failed for {ticker}: {e}")
        return 0.0


def rank_signals(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ranking score to signals.
    Higher score = better quality setup
    """
    if results_df.empty:
        return results_df
    
    df = results_df.copy()
    
    # Calculate relative strength for each ticker
    print("Calculating relative strength scores...")
    df["relative_strength"] = df["ticker"].apply(calculate_relative_strength)
    
    # Sort by RS (strongest momentum first)
    df = df.sort_values("relative_strength", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    
    return df