import yfinance as yf
import pandas as pd
import os
import requests
import json
from datetime import datetime
from src.exit_rules import SimpleExitRules
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
SHEET_ID = os.getenv("SHEET_ID")
SHEET_TAB_NAME = os.getenv("SHEET_TAB_NAME", "Positions")
GOOGLE_CREDS_JSON = os.getenv("GOOGLE_SHEETS_CREDENTIALS")

if not DISCORD_WEBHOOK:
    raise RuntimeError("Missing DISCORD_WEBHOOK_URL secret")
if not SHEET_ID or not GOOGLE_CREDS_JSON:
    raise RuntimeError("Missing SHEET_ID or GOOGLE_SHEETS_CREDENTIALS secret")

def read_tickers_from_sheet():
    """Read tickers, prices, dates, and sectors from Google Sheet."""
    try:
        # Parse credentials from JSON string
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        # Build service
        service = build('sheets', 'v4', credentials=creds)
        
        # Read data - now reading columns A through D
        range_name = f"{SHEET_TAB_NAME}!A:D"
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            print("⚠️  Sheet is empty")
            return []
        
        tickers = []
        for i, row in enumerate(values):
            # Skip header row
            if i == 0 or not row:
                continue
            
            ticker = row[0].strip().upper() if len(row) > 0 and row[0] else None
            
            # Parse entry price
            buy_price = None
            if len(row) > 1 and row[1]:
                try:
                    buy_price = float(str(row[1]).strip())
                except ValueError:
                    print(f"⚠️  Invalid price for {ticker}: '{row[1]}'")
            
            # Parse signal date
            signal_date = None
            if len(row) > 2 and row[2]:
                try:
                    # Try parsing the date
                    signal_date = pd.to_datetime(row[2]).date()
                except:
                    print(f"⚠️  Invalid date for {ticker}: '{row[2]}'")
            
            # Get sector
            sector = row[3].strip() if len(row) > 3 and row[3] else None
            
            if ticker:
                tickers.append((ticker, buy_price, signal_date, sector))
        
        return tickers
        
    except Exception as e:
        print(f"❌ Error reading Google Sheet: {e}")
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
    
    # Read tickers from Google Sheet
    tickers = read_tickers_from_sheet()
    print(f"Monitoring {len(tickers)} tickers from Google Sheet\n")
    
    alerts = []
    status_data = []  # Store full data for sorting
    
    for ticker, buy_price, signal_date, sector in tickers:
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
                
                # Calculate distance to target
                distance_to_target = ((target - latest_close) / latest_close) * 100
                
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
                    # Store data for sorting
                    status_data.append({
                        'ticker': ticker,
                        'pnl_pct': pnl_pct,
                        'days_held': days_held,
                        'distance_to_target': distance_to_target,
                        'sector': sector
                    })
                    
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
        if status_data:
            # Calculate portfolio average
            avg_pnl = sum(d['pnl_pct'] for d in status_data) / len(status_data)
            
            # Sort by P&L descending
            status_data.sort(key=lambda x: x['pnl_pct'], reverse=True)
            
            # Build status lines with enhanced info
            status_lines = []
            for d in status_data:
                line = f"{d['ticker']}: {d['pnl_pct']:+.1f}%"
                if d['days_held']:
                    line += f" (Day {d['days_held']}/10)"
                # Add emoji if close to target
                if d['distance_to_target'] < 1.0:
                    line += " 🎯"
                status_lines.append(line)
            
            status_body = f"✅ **All positions healthy - Portfolio avg: {avg_pnl:+.1f}%**\n\n" + "\n".join(status_lines)
        else:
            status_body = "✅ **No positions to monitor**"
            
        print(f"\n{status_body}\n")
        send_discord_alert(status_body)

if __name__ == "__main__":
    main()
