import yfinance as yf
import pandas as pd
from email.mime.text import MIMEText
import smtplib
import os

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("APP_PASSWORD")

if not EMAIL or not PASSWORD:
    raise RuntimeError("Missing email secrets")

TICKER_FILE = "tickerAlert.txt"

def read_tickers():
    tickers = []
    with open(TICKER_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            ticker = parts[0].strip().upper()
            buy_price = float(parts[1].strip()) if len(parts) > 1 else None
            tickers.append((ticker, buy_price))
    return tickers

def send_email_alert(subject, body, to_email):

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, [EMAIL], msg.as_string())

def main():
    tickers = read_tickers()
    alerts = []

    for ticker, buy_price in tickers:
        df = yf.download(ticker, period="3mo", interval="1d", progress=False)
        if df.empty or len(df) < 50:
            continue

        df["SMA50"] = df["Close"].rolling(50).mean()
        latest_close = df["Close"].iloc[-1]
        latest_sma50 = df["SMA50"].iloc[-1]

        if latest_close < latest_sma50:
            alerts.append(f"{ticker} below SMA50: Close={latest_close:.2f}, SMA50={latest_sma50:.2f}")

        if buy_price and latest_close < buy_price:
            alerts.append(f"{ticker} below buy price: Close={latest_close:.2f}, Bought at {buy_price:.2f}")

    if alerts:
        send_email_alert(
            subject="SwingTrade Alert",
            body="\n".join(alerts),
            to_email=EMAIL
        )
        print("\n".join(alerts))
    else:
        print("No alerts triggered.")

if __name__ == "__main__":
    main()
