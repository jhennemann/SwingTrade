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
    """Read tickers and prices from Google Sheet."""
    try:
        # Parse credentials from JSON string
        creds_dict = json.loads(GOOGLE_CREDS_JSON)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        
        # Build service
        service = build('sheets', 'v4', credentials=creds)
        
        # Read data
        range_name = f"{SHEET_TAB_NAME}!A:B"
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
            
            ticker = row[0].strip().upper() if len(row) > 0 else None
            buy_price = None
            
            if len(row) > 1 and row[1].strip():
                try:
                    buy_price = float(row[1].strip())
                except ValueError:
                    print(f"⚠️  Invalid price for {ticker}: '{row[1]}'")
            
            if ticker:
                tickers.append((ticker, buy_price))
        
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
    status_lines = []
    
    for ticker, buy_price in tickers:
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
                
                # Alert if stop loss hit
                if latest_close <= stop:
                    alerts.append(
                        f"🛑 **{ticker} HIT STOP LOSS**\n"
                        f"   Entry: ${buy_price:.2f} | Current: ${latest_close:.2f} ({pnl_pct:+.1f}%)\n"
                        f"   Stop: ${stop:.2f}"
                    )
                # Alert if profit target hit
                elif latest_close >= target:
                    alerts.append(
                        f"🎯 **{ticker} HIT PROFIT TARGET**\n"
                        f"   Entry: ${buy_price:.2f} | Current: ${latest_close:.2f} ({pnl_pct:+.1f}%)\n"
                        f"   Target: ${target:.2f}"
                    )
                # Track status for healthy positions
                else:
                    status_lines.append(f"{ticker}: {pnl_pct:+.1f}%")
                    print(f"✓ {ticker}: ${latest_close:.2f} | P&L: {pnl_pct:+.1f}% | Stop: ${stop:.2f} | Target: ${target:.2f}")
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
        status_body = "✅ **No alerts triggered - all positions healthy**\n\n" + "\n".join(status_lines)
        print(f"\n{status_body}\n")
        send_discord_alert(status_body)

if __name__ == "__main__":
    main()