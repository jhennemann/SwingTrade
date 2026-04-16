import os
import glob
import pandas as pd
from datetime import date
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_KEY"]
)

BACKFILL_FROM = date(2026, 3, 15)  # change this to when the error started

# Find all scan result CSVs in the data/charts directory
csv_files = glob.glob("data/charts/*/*/*/scan_results_*.csv")
csv_files.sort()

print(f"Found {len(csv_files)} CSV files\n")

for csv_path in csv_files:
    df = pd.read_csv(csv_path)

    if df.empty:
        print(f"Skipping {csv_path} — empty")
        continue

    run_date = df["last_date"].iloc[0]

    # Skip dates before our backfill start
    if pd.to_datetime(run_date).date() < BACKFILL_FROM:
        continue

    # Check if this date already exists in Supabase
    existing = supabase.table("signals").select("ticker").eq("last_date", run_date).execute()
    if existing.data:
        print(f"Skipping {run_date} — already in Supabase ({len(existing.data)} rows)")
        continue

    records = df.to_dict(orient="records")
    for record in records:
        for k, v in record.items():
            if pd.isna(v):
                record[k] = None

    supabase.table("signals").insert(records).execute()
    print(f"✓ Pushed {len(records)} signals for {run_date}")

print("\nBackfill complete.")