import os
import pandas as pd
from supabase import create_client
from src.reporting import PDFGalleryExporter
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])

# Fetch winning trades
response = supabase.table("signals").select("*").filter("win_loss", "gt", 0).execute()
signals = pd.DataFrame(response.data)
signals = signals.sort_values("win_loss", ascending=False)

print(f"Found {len(signals)} winning signals")

chart_paths = []
missing = []

for _, row in signals.iterrows():
    ticker = row.get("ticker")
    signal_date_raw = row.get("most_recent_signal_date")

    if not ticker or not signal_date_raw:
        missing.append(f"SKIPPED — missing ticker or date: {row.get('id')}")
        continue

    signal_date = pd.to_datetime(signal_date_raw)
    

    path = (
        f"data/charts/"
        f"{signal_date.year:04d}/"
        f"{signal_date.month:02d}/"
        f"{signal_date.date().isoformat()}/"
        f"{ticker}/pullback_setup.png"
    )

    if os.path.exists(path):
        chart_paths.append(path)
    else:
        missing.append(path)

print(f"Found {len(chart_paths)} charts, missing {len(missing)}")

if missing:
    print("\nMissing charts:")
    for p in missing:
        print(f"  {p}")

if chart_paths:
    exporter = PDFGalleryExporter(cols=2, rows=2)
    pdf_path = "data/charts/winners_gallery.pdf"
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
    exporter.export(
        image_paths=chart_paths,
        output_pdf_path=pdf_path,
        title="Winning Trades Gallery",
        subtitle=f"{len(chart_paths)} winning trades",
    )
    print(f"\nSaved: {pdf_path}")
else:
    print("No charts found to export")