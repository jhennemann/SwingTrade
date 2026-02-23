import yfinance as yf
import pandas as pd
import os
import requests
from datetime import datetime
from src.exit_rules import SimpleExitRules
from io import BytesIO

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
ONEDRIVE_URL = os.getenv("ONEDRIVE_EXCEL_URL")

if not DISCORD_WEBHOOK or not ONEDRIVE_URL:
    raise RuntimeError("Missing DISCORD_WEBHOOK_URL or ONEDRIVE_EXCEL_URL secret")

def read_tickers_from_excel():
    """Read tickers and prices from OneDrive Excel file."""
    try:
        # Download Excel file from OneDrive
        response = requests.get(ONEDRIVE_URL, timeout=30)
        response.raise_for_status()
        
        # Read Excel file from downloaded content
        df = pd.read_excel(BytesIO(response.content), sheet_name="Positions")
        
        tickers = []
        for _, row in df.iterrows():
            ticker = str(row.get('ticker', '')).strip().upper()
            entry_price = row.get('entry_price', None)
            signal_date = row.get('signal_date', None)
            
            if not ticker or ticker == 'NAN':
                continue
            
            # Convert entry_price to float if it exists
            if pd.notna(entry_price):
                try:
                    entry_price = float(entry_price)
                except:
                    entry_price = None
            else:
                entry_price = None
            
            # Convert signal_date to string if it exists
            if pd.notna(signal_date):
                signal_date = pd.to_datetime(signal_date).date()
            else:
                signal_date = None
            
            tickers.append((ticker, entry_price, signal_date))
        
        print(f"✓ Loaded {len(tickers)} positions from OneDrive Excel")
        return tickers
        
    except Exception as e:
        print(f"❌ Error reading Excel from OneDrive: {e}")
        raise

def send_discord_alert(message: str):
    """Send message to Discord via webhook."""
    try:
        response = requests.post(
            DISCORD_WEBHOOK,
            json={"content": message},
            timeout=10
        )
        response.raise_for_status()
        print(f"✅ Alert sent to Discord")
    except Exception as e:
        print(f"❌ Failed to send Discord message: {e}")
        raise

def main():
    print(f"=== SwingTrade Alerts - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    # Create exit rules calculator
    exit_rules = SimpleExitRules(
        stop_loss_pct=0.02,
        profit_target_pct=0.07,
        max_hold_days=10
    )
    
    # Read tickers from OneDrive Excel
    tickers = read_tickers_from_excel()
    print(f"Monitoring {len(tickers)} tickers from OneDrive\n")
    
    alerts = []
    status_lines = []
    
    for ticker, buy_price, signal_date in tickers:
        try:
            # Download data
            df = yf.download(ticker, period="3mo", interval="1d", progress=False, auto_adjust=False)
            
            if df.empty or len(df) < 50:
                print(f"⚠️  {ticker}: Insufficient data (need 50+ days)")
                continue
            
            # Flatten MultiIndex if needed
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Calculate SMA50
            df["SMA50"] = df["Close"].rolling(50).mean()
            
            latest_close = float(df["Close"].iloc[-1])
            latest_sma50 = float(df["SMA50"].iloc[-1])
            
            # Alert 1: Below SMA50
            if latest_close < latest_sma50:
                pct_below = ((latest_sma50 - latest_close) / latest_sma50) * 100
                alerts.append(
                    f"🔴 **{ticker}** below SMA50\n"
                    f"   Close: ${latest_close:.2f} | SMA50: ${latest_sma50:.2f} ({pct_below:.1f}% below)"
                )
            
            # Alert 2: Position tracking (if you have entry price)
            if buy_price:
                # Calculate P&L
                pnl_pct = ((latest_close - buy_price) / buy_price) * 100
                
                # Calculate exit levels
                exits = exit_rules.calculate_exits(buy_price)
                stop = exits['stop_loss']
                target = exits['profit_target']
                
                # Calculate days held if signal_date exists
                days_held = None
                if signal_date:
                    days_held = (datetime.now().date() - signal_date).days
                
                # Alert if stop loss hit
                if latest_close <= stop:
                    alert_text = f"🛑 **{ticker} HIT STOP LOSS**\n   Entry: ${buy_price:.2f} | Current: ${latest_close:.2f} ({pnl_pct:+.1f}%)\n   Stop: ${stop:.2f}"
                    if days_held:
                        alert_text += f" | Day {days_held}/10"
                    alerts.append(alert_text)
                    
                # Alert if profit target hit
                elif latest_close >= target:
                    alert_text = f"🎯 **{ticker} HIT PROFIT TARGET**\n   Entry: ${buy_price:.2f} | Current: ${latest_close:.2f} ({pnl_pct:+.1f}%)\n   Target: ${target:.2f}"
                    if days_held:
                        alert_text += f" | Day {days_held}/10"
                    alerts.append(alert_text)
                    
                # Track status for healthy positions
                else:
                    status_text = f"{ticker}: {pnl_pct:+.1f}%"
                    if days_held:
                        status_text += f" (Day {days_held}/10)"
                    status_lines.append(status_text)
                    
                    log_text = f"✓ {ticker}: ${latest_close:.2f} | P&L: {pnl_pct:+.1f}% | Stop: ${stop:.2f} | Target: ${target:.2f}"
                    if days_held:
                        log_text += f" | Day {days_held}/10"
                    print(log_text)
            else:
                # No entry price, just show current price
                print(f"✓ {ticker}: ${latest_close:.2f} (SMA50: ${latest_sma50:.2f})")
        
        except Exception as e:
            print(f"❌ {ticker}: Error - {e}")
    
    # Send Discord message
    if alerts:
        alert_body = "🚨 **SwingTrade Alerts**\n\n" + "\n\n".join(alerts)
        print(f"\n{'='*60}")
        print("🚨 ALERTS TRIGGERED:")
        print(alert_body)
        print(f"{'='*60}\n")
        send_discord_alert(alert_body)
    else:
        # Calculate portfolio average
        if status_lines:
            # Extract just the percentages for averaging
            pnl_values = []
            for line in status_lines:
                try:
                    pnl_str = line.split(':')[1].split('%')[0].strip()
                    pnl_values.append(float(pnl_str))
                except:
                    pass
            
            avg_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else 0
            
            # Sort by P&L descending
            status_lines_sorted = sorted(status_lines, key=lambda x: float(x.split(':')[1].split('%')[0]), reverse=True)
            
            status_body = f"✅ **All positions healthy - Portfolio avg: {avg_pnl:+.1f}%**\n\n" + "\n".join(status_lines_sorted)
        else:
            status_body = "✅ **No positions to monitor**"
            
        print(f"\n{status_body}\n")
        send_discord_alert(status_body)

if __name__ == "__main__":
    main()