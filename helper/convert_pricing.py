import os
import pandas as pd
import json

# go up one level from current working dir
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

CSV_FILE = os.path.join(DATA_DIR, "pricing.csv")
JSON_FILE = os.path.join(DATA_DIR, "pricing.json")

print("Looking for CSV at:", CSV_FILE)

df = pd.read_csv(CSV_FILE)

pricing = {}

for _, row in df.iterrows():
    tow_type = str(row["tow_type"]).strip()
    service = str(row["service"]).strip()

    entry = {
        "label": str(row["label"]).strip() if not pd.isna(row["label"]) else "",
        "rate": int(row["rate"]) if not pd.isna(row["rate"]) else 0,
        "mileage": int(row["mileage"]) if not pd.isna(row["mileage"]) else 0,
        "includes": int(row["includes"]) if not pd.isna(row["includes"]) else 0,
    }

    if "comment" in row and not pd.isna(row["comment"]):
        entry["comment"] = str(row["comment"]).strip()

    if tow_type not in pricing:
        pricing[tow_type] = {}
    pricing[tow_type][service] = entry

# Save JSON
os.makedirs(DATA_DIR, exist_ok=True)
with open(JSON_FILE, "w") as f:
    json.dump(pricing, f, indent=2)

print(f"✅ pricing.json created successfully at {JSON_FILE}")
