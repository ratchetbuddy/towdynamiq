import csv
import json
import os
from collections import defaultdict
import re

def parse_condition(expr: str):
    expr = expr.strip()

    # Remove outer parentheses
    if expr.startswith("(") and expr.endswith(")"):
        return parse_condition(expr[1:-1].strip())

    # Handle OR at top level
    parts = split_top_level(expr, "|")
    if len(parts) > 1:
        return {"type": "OR", "triggers": [parse_condition(p) for p in parts]}

    # Handle AND at top level
    parts = split_top_level(expr, "&")
    if len(parts) > 1:
        return {"type": "AND", "triggers": [parse_condition(p) for p in parts]}

    # Base case: single token (normalize to dict!)
    return {"type": "SINGLE", "triggers": [expr.strip()]}

def split_top_level(expr: str, op: str):
    """Split expression by operator, ignoring parentheses nesting."""
    parts = []
    depth = 0
    start = 0
    for i, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == op and depth == 0:
            parts.append(expr[start:i].strip())
            start = i + 1
    parts.append(expr[start:].strip())
    return [p for p in parts if p]

import csv
import json
import os
from collections import defaultdict

def parse_condition(expr: str):
    expr = expr.strip()

    if expr.startswith("(") and expr.endswith(")"):
        return parse_condition(expr[1:-1].strip())

    parts = split_top_level(expr, "|")
    if len(parts) > 1:
        return {"type": "OR", "triggers": [parse_condition(p) for p in parts]}

    parts = split_top_level(expr, "&")
    if len(parts) > 1:
        return {"type": "AND", "triggers": [parse_condition(p) for p in parts]}

    return {"type": "SINGLE", "triggers": [expr.strip()]}

def split_top_level(expr: str, op: str):
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(expr):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == op and depth == 0:
            parts.append(expr[start:i].strip())
            start = i + 1
    parts.append(expr[start:].strip())
    return [p for p in parts if p]

def collect_all_modifiers(csv_file):
    all_mods = set()
    with open(csv_file, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            applied = row.get("applied_modifiers", "")
            all_mods.update(m.strip() for m in applied.split(",") if m.strip())
    return sorted(all_mods)  # keep stable order

def pricing_csv_to_json(csv_file, json_file):
    services_by_type = defaultdict(dict)
    units_map = defaultdict(lambda: defaultdict(dict))
    # ✅ pass 1: get global modifiers
    all_modifiers = collect_all_modifiers(csv_file)

    with open(csv_file, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tow_type = row["tow_type"].strip()
            service_code = row["service_code"].strip()
            pricing_type = row["pricing_type"].strip().lower()
            dropdown_rank = int(row["dropdown_rank"] or 0)

            # ✅ build modifiers with full coverage
            row_mods = {m.strip(): True for m in row["applied_modifiers"].split(",") if m.strip()}
            modifiers = {mod: row_mods.get(mod, False) for mod in all_modifiers}

            # --- Common object skeleton ---
            base_obj = {
                "label": row["service_label"],
                "pricing_type": pricing_type,
                "dropdown_rank": dropdown_rank,
                "rules": [],
                "modifiers": modifiers
            }

            # --- Handle per_unit ---
            if pricing_type == "per_unit":
                unit_code = row["unit_code"].strip()
                unit_label = row["unit_label"].strip()
                unit_price = float(row["unit_price"]) if row["unit_price"] else 0

                units_map[tow_type][service_code][unit_code] = {
                    "label": unit_label,
                    "price": unit_price
                }

                if service_code not in services_by_type[tow_type]:
                    service_obj = {
                        **base_obj,
                        "base_rate": float(row["base_rate"] or 0),
                        "mileage": int(row["mileage_rate"] or 0),
                        "includes": int(row["included_miles"] or 0),
                        "accident": {"hook": float(row["accident_hook"])} if row.get("accident_hook") else None,
                        "units": units_map[tow_type][service_code],
                        "requires_inputs": ["unit_type", "count"]
                    }
                    services_by_type[tow_type][service_code] = service_obj
                else:
                    services_by_type[tow_type][service_code]["units"] = units_map[tow_type][service_code]
                continue

            # --- Handle time_based ---
            if pricing_type == "time_based":
                service_obj = {
                    **base_obj,
                    "base_rate": float(row["base_rate"] or 0),
                    "includes_time": int(row["included_minutes"] or 0),
                    "increment_minutes": int(row["increment_minutes"] or 0),
                    "rate_per_increment": float(row["increment_price"] or 0),
                    "requires_inputs": ["duration_minutes"]
                }
                services_by_type[tow_type][service_code] = service_obj
                continue

            # --- Handle flat (default) ---
            service_obj = {
                **base_obj,
                "base_rate": float(row["base_rate"] or 0),
                "mileage": int(row["mileage_rate"] or 0),
                "includes": int(row["included_miles"] or 0),
                "requires_inputs": []
            }

            # Accident hook
            if row.get("accident_hook"):
                try:
                    service_obj["accident"] = {"hook": float(row["accident_hook"])}
                except ValueError:
                    pass

            # Addon rules
            if row.get("addon_price") and row.get("addon_trigger_service_code"):
                trigger_expr = row["addon_trigger_service_code"].strip()
                condition = parse_condition(trigger_expr)
                service_obj["rules"].append({
                    "addon_rate": float(row["addon_price"]),
                    "condition": condition
                })

            services_by_type[tow_type][service_code] = service_obj

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(services_by_type, f, indent=2)

    print(f"✅ pricing JSON saved to {json_file}")


def update_vehicle_location_from_csv(csv_file: str, json_file: str):
    """
    Replaces the `vehicle_location` section of dynamic_modifiers.json
    with values from vehicle_location.csv
    """
    # Step 1: Load current JSON
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Step 2: Build new vehicle_location dict from CSV
    new_vehicle_location = {}
    with open(csv_file, mode="r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            road_type = row["Road Type"].strip()
            lane = row["Lane location"].strip()
            upcharge_str = row["Upcharge"].strip().replace("%", "")

            try:
                upcharge = float(upcharge_str) / 100.0
            except ValueError:
                upcharge = 0.0

            if road_type not in new_vehicle_location:
                new_vehicle_location[road_type] = {
                    "label": road_type,
                    "lanes": {}
                }

            new_vehicle_location[road_type]["lanes"][lane] = {
                "label": lane,
                "upcharge": upcharge
            }

    # Step 3: Replace in JSON
    data["vehicle_location"] = new_vehicle_location

    # Step 4: Save back
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"✅ vehicle_location updated in {json_file}")

def update_subtotal_upcharge_from_csv(csv_file: str, json_file: str):
    """
    Reads subtotal upcharge bands from a CSV file and updates
    the 'subtotal_upcharge_bands' section in dynamic_modifiers.json.
    
    CSV must have columns:
      subtotal_range, subtotal_min, subtotal_max, max_upcharge
    """
    # Step 1: Load current JSON
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Step 2: Build subtotal bands dict
    subtotal_bands = {}

    with open(csv_file, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row["subtotal_range"].strip()
            min_val = float(row["subtotal_min"])
            max_val = float(row["subtotal_max"])
            upcharge = float(row["max_upcharge"])

            key = f"{int(min_val)}-{int(max_val)}"
            subtotal_bands[key] = {
                "label": label,
                "min": min_val,
                "max": max_val,
                "max_upcharge": upcharge
            }

    # Step 3: Replace in JSON
    data["subtotal_upcharge_bands"] = subtotal_bands

    # Step 4: Save back
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"✅ upcharge_bands updated in {json_file}")


def makeModelCsv_to_json(csv_file: str, json_file: str):
    """
    Convert car CSV into nested JSON structure.

    Args:
        csv_file (str): Path to input CSV file.
        json_file (str): Path where JSON will be written.
    """

    # use defaultdict to auto-create nested dicts
    car_data = defaultdict(lambda: {"label": "", "models": {}})

    with open(csv_file, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            make = row["make"].strip()
            model = row["model"].strip()
            car_type = row["car_type"].strip()
            upcharge = float(row["upcharge_percentage"].strip())

            # ensure make exists
            if not car_data[make]["label"]:
                car_data[make]["label"] = make

            # add model details
            car_data[make]["models"][model] = {
                "label": model,
                "car_type": car_type,
                "upcharge_percentage": upcharge
            }

    # convert defaultdict to normal dict
    car_data = dict(car_data)

    # write JSON
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(car_data, f, indent=2, ensure_ascii=False)

    print(f"✅ make_model_modifiers JSON file created at {json_file}")

if __name__ == "__main__":
    base_dir = r"C:\Users\dthiya\OneDrive - Niagara Bottling, LLC\Documents\Dixit Thiya\towdynamiq\data"

    #Pricing2.0
    csv_file = os.path.join(base_dir, "pricing.csv")
    json_file = os.path.join(base_dir, "pricing.json")

    pricing_csv_to_json(csv_file, json_file)

    # Vehicle Location
    vehicle_csv = os.path.join(base_dir, "vehicle_location_modifiers.csv")
    modifiers_json = os.path.join(base_dir, "dynamic_modifiers.json")

    update_vehicle_location_from_csv(vehicle_csv, modifiers_json)

    # Upcharge Bands
    subtotal_csv = os.path.join(base_dir, "subtotal_upcharge_bands_modifiers.csv")
    modifiers_json = os.path.join(base_dir, "dynamic_modifiers.json")

    update_subtotal_upcharge_from_csv(subtotal_csv, modifiers_json)

    # make_model_modifiers.json Build

    make_model_csv = os.path.join(base_dir, "make_model_modifiers.csv")
    make_model_json = os.path.join(base_dir, "make_model_modifiers.json")
    makeModelCsv_to_json(make_model_csv, make_model_json)

