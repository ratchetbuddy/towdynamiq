import os, json, requests, math
from datetime import datetime, timedelta

API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")

# ------------------- Google Distance -------------------

def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {"origins": origin, "destinations": destination, "key": API_KEY, "units": "imperial"}
    response = requests.get(url, params=params)
    data = response.json()
    if data["status"] != "OK":
        raise Exception(f"Error from API: {data}")
    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise Exception(f"Error in element: {element}")

    distance_value = element["distance"]["value"]  # meters
    g_miles = distance_value / 1609.34
    return {
        "g_miles": round(g_miles, 1),
        "resolved_origin": data.get("origin_addresses", [""])[0],
        "resolved_destination": data.get("destination_addresses", [""])[0]
    }

# ------------------- JSON Loader -------------------

def load_json(filename):
    with open(os.path.join("data", filename), "r") as f:
        return json.load(f)

# ------------------- Mileage Buckets -------------------

def get_billable_miles(actual_miles: int, dynamic_modifiers: dict) -> int:
    mode = dynamic_modifiers["bucket_mileage_pricing"]["mode"]

    if mode == "tiers":
        for rng, values in dynamic_modifiers["bucket_mileage_pricing"]["tiers"].items():
            start, end = map(int, rng.split("-"))
            if start <= actual_miles <= end:
                return values["billable_miles"]
        return actual_miles

    elif mode == "pattern":
        rules = dynamic_modifiers["bucket_mileage_pricing"]["pattern"]
        if actual_miles <= 5:
            return 0
        start = rules["start"]
        step = rules["first_step"]
        cap = start + step - 1
        while cap < rules["max_miles"]:
            if actual_miles <= cap:
                return cap
            step += rules["step_growth"]
            start = cap + 1
            cap = start + step - 1
        return rules["max_miles"]

    raise ValueError(f"Unknown mileage mode: {mode}")

# ------------------- Condition Evaluation -------------------

def evaluate_condition(condition, selected_services):
    ctype = condition["type"]
    if ctype == "SINGLE":
        return any(trigger in selected_services for trigger in condition["triggers"])
    elif ctype == "AND":
        return all(evaluate_condition(child, selected_services) for child in condition["triggers"])
    elif ctype == "OR":
        return any(evaluate_condition(child, selected_services) for child in condition["triggers"])
    raise ValueError(f"Unknown condition type: {ctype}")

# Printed Explanation for evaluate_condition
# def evaluate_condition(condition, selected_services, depth=0):
#     indent = "  " * depth  # visual indent for nested levels
#     ctype = condition["type"]

#     print(f"{indent}Checking condition: {ctype} | triggers = {condition['triggers']}")

#     if ctype == "SINGLE":
#         result = any(trigger in selected_services for trigger in condition["triggers"])
#         print(f"{indent}→ SINGLE {condition['triggers']} in {selected_services}? {result}")
#         return result

#     elif ctype == "AND":
#         results = []
#         for child in condition["triggers"]:
#             result = evaluate_condition(child, selected_services, depth + 1)
#             results.append(result)
#         final = all(results)
#         print(f"{indent}→ AND results = {results} → {final}")
#         return final

#     elif ctype == "OR":
#         results = []
#         for child in condition["triggers"]:
#             result = evaluate_condition(child, selected_services, depth + 1)
#             results.append(result)
#         final = any(results)
#         print(f"{indent}→ OR results = {results} → {final}")
#         return final

#     else:
#         raise ValueError(f"Unknown condition type: {ctype}")

# ------------------- Pricing Calculators -------------------

def calc_flat(service, inputs):
    base_rate = service["base_rate"]
    miles = inputs.get("miles", 0)   # 👈 already bucketed miles
    includes = service.get("includes", 0)
    per_mile = service.get("mileage", 0)

    # charge = bucket miles - includes
    billable_miles = max(0, miles - includes)
    mileage_cost = billable_miles * per_mile
    total = base_rate + mileage_cost

    return {
        "subtotal": total,
        "hook_cost": base_rate,
        "mileage_cost": mileage_cost,
        "miles_charged": billable_miles,   # 👈 full billable miles
        "per_mile": per_mile,
        "includes": includes,
    }

def calc_per_unit(service, inputs):
    total = 0
    items = []

    # Loop through all defined unit types for this service (e.g. side_window, front_or_back_window)
    for unit_type, unit_info in service["units"].items():
        count = inputs.get(unit_type, 0)  # how many of this unit were requested
        if count > 0:
            unit_price = unit_info["price"]
            cost = unit_price * count
            total += cost
            items.append({
                "unit_type": unit_type,
                "label": unit_info["label"],   # e.g. "Side Windows"
                "count": count,                # e.g. 2
                "unit_price": unit_price,      # e.g. $20.0
                "cost": cost                   # e.g. $40.0
            })

    return {
        "subtotal": total,   # sum of all unit types
        "items": items       # 👈 exact breakdown for each unit type
    }



def calc_time_based(service, inputs):
    minutes = inputs.get("duration_minutes", 0)
    base_rate = service.get("base_rate", 0)
    included = service.get("includes_time", 0)
    increment = service.get("increment_minutes", 30)
    rate = service.get("rate_per_increment", 0)

    extra = max(0, minutes - included)
    increments = -(-extra // increment)  # ceil division
    extra_cost = increments * rate
    subtotal = base_rate + extra_cost

    return {
        "subtotal": subtotal,
        "hook": base_rate,
        "extra_minutes": extra,
        "increments": increments,
        "rate_per_increment": rate,
        "extra_cost": extra_cost
    }



PRICING_CALCULATORS = {
    "flat": calc_flat,
    "per_unit": calc_per_unit,
    "time_based": calc_time_based,
}

# ------------------- Breakdown Formatter -------------------

def format_breakdown(response_json):
    col_width = 25
    lines = []

    # Header
    lines.append(f"{'Tow Type:'.ljust(col_width)}{response_json['tow_type']}")
    lines.append(f"{'Original Pickup:'.ljust(col_width)}{response_json.get('source', '')}")
    lines.append(f"{'Pickup - TowDynamiq AI:'.ljust(col_width)}{response_json.get('source_resolved', '')}")
    lines.append(f"{'Original Drop:'.ljust(col_width)}{response_json.get('destination', '')}")
    lines.append(f"{'Drop - TowDynamiq AI:'.ljust(col_width)}{response_json.get('destination_resolved', '')}")
    lines.append(f"{'Actual Distance:'.ljust(col_width)}{response_json['distance_text_actual']}")
    lines.append(f"{'Rounded Distance:'.ljust(col_width)}{response_json['distance_text']}")
    lines.append(f"{'Bucket Mileage:'.ljust(col_width)}{response_json.get('bucket_miles', '')} mi")
    lines.append("-" * (col_width * 2))

    # Services
    for i, service in enumerate(response_json["services"], start=1):
        lines.append(f"Service {i}:".ljust(col_width) + f"{service['service']}")
        details = service.get("calc_details", {})

        if service["pricing_type"] == "flat":
            hook = details.get('hook_cost', 0)
            per_mile = details.get('per_mile', 0)
            includes = details.get('includes', 0)

            # Use rounded miles for "mileage cost" and standard quote
            actual_rounded = int(float(response_json['distance_text'].replace(" mi", "")))
            rounded_miles_charged = max(0, actual_rounded - includes)
            mileage_cost_rounded = rounded_miles_charged * per_mile
            standard_quote = hook + mileage_cost_rounded

            # Difference for bucket miles
            bucket_miles = response_json.get("bucket_miles", actual_rounded)
            diff_miles = max(0, bucket_miles - actual_rounded)
            diff_cost = diff_miles * per_mile

            # Print breakdown
            lines.append(f"{'Hook Charge:'.ljust(col_width)}${hook}")
            lines.append(
                f"{'Mileage Cost:'.ljust(col_width)}"
                f"${mileage_cost_rounded} ({rounded_miles_charged} @ ${per_mile}/mi)"
            )
            lines.append(f"{'Standard Quote:'.ljust(col_width)}${standard_quote}")
            lines.append(f"{'Total Upcharge %:'.ljust(col_width)}{service['combined_upcharge_pct']*100:.1f}%")
            lines.append(f"{'Upcharge Amount:'.ljust(col_width)}${service['upcharge_amount']}")
            if diff_miles > 0:
                lines.append(
                    f"{'Mileage Upcharge:'.ljust(col_width)}"
                    f"${diff_cost} ({diff_miles} @ ${per_mile}/mi)"
                )

        elif service["pricing_type"] == "per_unit":
            for unit in details.get("items", []):
                lines.append(
                    f"{unit['label']+':':{col_width}}{unit['count']} × ${unit['unit_price']} = ${unit['cost']}"
                )

        elif service["pricing_type"] == "time_based":
            lines.append(f"{'Hook Charge:'.ljust(col_width)}${details.get('hook', 0)}")
            lines.append(
                f"{'Extra Time Charge:'.ljust(col_width)}"
                f"${details.get('extra_cost', 0)} ({details.get('increments', 0)} × ${details.get('rate_per_increment', 0)})"
            )
        
        # ✅ Common upcharge section (works for all pricing types)
        non_zero_mods = {k: v for k, v in service.get("upcharges", {}).items() if v > 0}
        if non_zero_mods:
            lines.append("  Applied Upcharges:")
            for k, v in non_zero_mods.items():
                pct = f"{round(v * 100, 1)}%"
                label = k.replace("_", " ").title()
                lines.append(f"   - {label.ljust(col_width-6)} {pct}")



        # Always show final TowDynamiq quote
        lines.append(f"{'TowDynamiq Quote:'.ljust(col_width)}${service['todynamiq_quote']}")
        lines.append("-" * (col_width * 2))

    # Totals
    lines.append(f"{'Time Used:'.ljust(col_width)}{response_json.get('calculation_time', '')}")
    lines.append(f"{'Total Standard Quote:'.ljust(col_width)}${response_json['standard_quote']}")
    lines.append(f"{'Overall % Change:'.ljust(col_width)}{response_json['overall_pct_chng']}%")
    lines.append(f"{'Total TowDynamiq Quote:'.ljust(col_width)}${response_json['todynamiq_quote']}")

    return "\n".join(lines)


def get_max_upcharge_cap(subtotal: float, bands: dict) -> float:
    for key, band in bands.items():
        if band["min"] <= subtotal <= band["max"]:
            return band["max_upcharge"]
    return 0.25  # fallback default
