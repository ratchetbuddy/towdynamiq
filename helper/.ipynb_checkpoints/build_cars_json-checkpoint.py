import os
import pandas as pd
import json

# go up one level from current working dir (same pattern as your pricing script)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

CSV_FILE = os.path.join(DATA_DIR, "cars.csv")
JSON_FILE = os.path.join(DATA_DIR, "cars.json")

print("Looking for CSV at:", CSV_FILE)

df = pd.read_csv(CSV_FILE, sep="\t|,", engine="python")  # supports tab or comma CSVs

cars = {}

for _, row in df.iterrows():
    make = str(row["make"]).strip()
    model = str(row["model"]).strip()
    car_type = str(row["car_type"]).strip()
    upcharge = float(row["upcharge_percentage"])

    # Initialize make if not present
    if make not in cars:
        cars[make] = {
            "label": make,
            "models": {}
        }

    # Add model under make
    cars[make]["models"][model] = {
        "label": model,
        "car_type": car_type,
        "upcharge_percentage": upcharge
    }

# Save JSON
os.makedirs(DATA_DIR, exist_ok=True)
with open(JSON_FILE, "w") as f:
    json.dump(cars, f, indent=2)

print(f"✅ cars.json created successfully at {JSON_FILE}")
