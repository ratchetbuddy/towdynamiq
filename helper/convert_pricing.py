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

def csv_to_json(csv_file, json_file):
    services_by_type = defaultdict(dict)
    units_map = defaultdict(lambda: defaultdict(dict))  # tow_type -> service_code -> units

    with open(csv_file, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tow_type = row["tow_type"].strip()
            service_code = row["service_code"].strip()
            pricing_type = row["pricing_type"].strip().lower()

            # --- Build modifiers dict ---
            modifiers = {m.strip(): True for m in row["applies_modifiers"].split(",") if m.strip()}
            for mod in ["weather","lane","make_model","truck_utilization","time_of_day","holiday"]:
                modifiers.setdefault(mod, False)

            # --- Handle per_unit services ---
            if pricing_type == "per_unit":
                units_map[tow_type][service_code][row["unit_code"]] = float(row["unit_price"]) if row["unit_price"] else 0
                if service_code not in services_by_type[tow_type]:
                    services_by_type[tow_type][service_code] = {
                        "label": row["service_label"],
                        "pricing_type": "per_unit",
                        "units": units_map[tow_type][service_code],
                        "requires_inputs": ["unit_type", "count"],
                        "modifiers": modifiers
                    }
                else:
                    services_by_type[tow_type][service_code]["units"] = units_map[tow_type][service_code]
                continue

            # --- Handle time_based services ---
            if pricing_type == "time_based":
                services_by_type[tow_type][service_code] = {
                    "label": row["service_label"],
                    "pricing_type": "time_based",
                    "base_rate": float(row["base_rate"] or 0),
                    "includes_time": int(row["included_minutes"] or 0),
                    "increment_minutes": int(row["increment_minutes"] or 0),
                    "rate_per_increment": float(row["increment_price"] or 0),
                    "requires_inputs": ["duration_minutes"],
                    "modifiers": modifiers
                }
                continue

            # --- Default flat pricing ---
            service_obj = {
                "label": row["service_label"],
                "pricing_type": "flat",
                "base_rate": float(row["base_rate"] or 0),
                "mileage": int(row["mileage_rate"] or 0),
                "includes": int(row["included_miles"] or 0),
                "rules": [],
                "requires_inputs": [],
                "modifiers": modifiers
            }

            # Accident pricing if provided
            if row.get("accident_hook"):
                try:
                    accident_hook = float(row["accident_hook"])
                    service_obj["accident"] = {
                        "hook": accident_hook
                    }
                except ValueError:
                    pass

            # Handle addon rules
            if row.get("addon_price") and row.get("addon_trigger_service_code"):
                trigger_expr = row["addon_trigger_service_code"].strip()
                condition = parse_condition(trigger_expr)
                service_obj["rules"].append({
                    "addon_rate": float(row["addon_price"]),
                    "condition": condition
                })

            services_by_type[tow_type][service_code] = service_obj

    # --- Save JSON file ---
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(services_by_type, f, indent=2)

    print(f"✅ JSON saved to {json_file}")



if __name__ == "__main__":
    base_dir = r"E:\towdynamiq\git\towdynamiq\data"
    csv_file = os.path.join(base_dir, "pricing2.0.csv")
    json_file = os.path.join(base_dir, "pricing2.0.json")

    csv_to_json(csv_file, json_file)
