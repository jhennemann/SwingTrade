import yfinance as yf
import pandas as pd
from email.mime.text import MIMEText
import smtplib
import os
from datetime import datetime

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("APP_PASSWORD")
PHONE = os.getenv("PHONE")

if not EMAIL or not PASSWORD or not PHONE:
    raise RuntimeError("Missing EMAIL, APP_PASSWORD, or PHONE secrets")

TICKER_FILE = "tickerAlert.txt"

def read_tickers():
    """Read tickers and optional buy prices from file."""
    if not os.path.exists(TICKER_FILE):
        raise FileNotFoundError(f"{TICKER_FILE} not found in repo")
    
    tickers = []
    with open(TICKER_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.lower().startswith("ticker"):
                continue
            
            parts = line.split(",")
            ticker = parts[0].strip().upper()
            buy_price = None
            
            if len(parts) > 1 and parts[1].strip():
                try:
                    buy_price = float(parts[1].strip())
                except ValueError:
                    print(f"⚠️  Invalid price for {ticker}: '{parts[1].strip()}'")
            
            tickers.append((ticker, buy_price))
    
    return tickers

def send_email_alert(subject, body, to_email):
    """Send email via Gmail SMTP."""
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"SwingTrade Alert <{EMAIL}>"
        msg["To"] = to_email
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, [to_email], msg.as_string())
        
        print(f"✅ Alert sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise

def main():
    print(f"=== SwingTrade Alerts - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    # Read tickers
    tickers = read_tickers()
    print(f"Monitoring {len(tickers)} tickers\n")
    
    alerts = []
    
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
                    f"🔴 {ticker} below SMA50\n"
                    f"   Close: ${latest_close:.2f} | SMA50: ${latest_sma50:.2f} ({pct_below:.1f}% below)"
                )
            
            # Alert 2: Below buy price
            if buy_price and latest_close < buy_price:
                loss_pct = ((buy_price - latest_close) / buy_price) * 100
                alerts.append(
                    f"📉 {ticker} below buy price\n"
                    f"   Current: ${latest_close:.2f} | Bought: ${buy_price:.2f} ({loss_pct:.1f}% loss)"
                )
            
            print(f"✓ {ticker}: ${latest_close:.2f} (SMA50: ${latest_sma50:.2f})")
        
        except Exception as e:
            print(f"❌ {ticker}: Error - {e}")
    
    # Send alerts
    if alerts:
        alert_body = "\n\n".join(alerts)
        print(f"\n{'='*60}")
        print("🚨 ALERTS TRIGGERED:")
        print(alert_body)
        print(f"{'='*60}\n")
        
        send_email_alert(
            subject=f"SwingTrade Alert - {len(alerts)} Warning(s)",
            body=alert_body,
            to_email=PHONE
        )
    else:
        print("\n✅ No alerts triggered - all positions healthy")

if __name__ == "__main__":
    main()