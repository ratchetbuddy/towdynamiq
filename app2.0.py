from flask import Flask, render_template, request, jsonify, Response
import os
import json
import requests
from collections import OrderedDict
from datetime import datetime, timedelta   # ✅ add timedelta here

app = Flask(__name__)


API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY_HERE")

# print("Google Maps API Key loaded:", bool(API_KEY))   # ✅ True if loaded
# print("Value (first 10 chars):", API_KEY[:10] if API_KEY else "NOT SET")

def get_distance(origin, destination):
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "key": API_KEY,
        "units": "imperial"  # miles
    }
    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] != "OK":
        raise Exception(f"Error from API: {data}")

    element = data["rows"][0]["elements"][0]
    if element["status"] != "OK":
        raise Exception(f"Error in element: {element}")

    # Distance
    distance_value = element["distance"]["value"]  # meters
    g_miles = distance_value / 1609.34

    # Round consistently to 1 decimal place
    miles_rounded = round(g_miles, 1)                # numeric
    distance_text = f"{miles_rounded:.1f} mi"      # string with 1 decimal

    # Normalized addresses (Google's best guess)
    resolved_origin = data.get("origin_addresses", [""])[0]
    resolved_destination = data.get("destination_addresses", [""])[0]

    return {
        "g_miles": miles_rounded,                # e.g. 21.2
        "distance_text": distance_text,        # e.g. "21.2 mi"
        "resolved_origin": resolved_origin,
        "resolved_destination": resolved_destination
    }


def format_breakdown(response_json):
    col_width = 25
    lines = []

    # Header
    lines.append(f"{'Tow Type:'.ljust(col_width)}{response_json['tow_type']}")
    lines.append(f"{'Original Pickup:'.ljust(col_width)}{response_json.get('source', '')}")
    lines.append(f"{'Pickup - TowDynamiq AI:'.ljust(col_width)}{response_json.get('source_resolved', '')}")
    lines.append(f"{'Original Drop:'.ljust(col_width)}{response_json.get('destination', '')}")
    lines.append(f"{'Drop - TowDynamiq AI:'.ljust(col_width)}{response_json.get('destination_resolved', '')}")
    lines.append(f"{'Distance:'.ljust(col_width)}{response_json['distance_text']}")
    lines.append("-" * (col_width * 2))

    # Services (numbered)
    for i, service in enumerate(response_json["services"], start=1):
        lines.append(f"Service {i}:".ljust(col_width) + f"{service['service']}")
        lines.append(f"{'Hook Fee:'.ljust(col_width)}${service['hook']}")
        lines.append(
            f"{'Miles Charged:'.ljust(col_width)}"
            f"{service['mileage']} @ ${service['per_mile']}/mile = ${service['mileage_cost']}"
        )
        lines.append(f"{'Included Miles:'.ljust(col_width)}{service['includes']}")
        lines.append("-" * (col_width * 2))

    # Upcharges (only show if any > 0)
    non_zero_upcharges = {k: v for k, v in response_json["upcharges"].items() if v > 0}
    if non_zero_upcharges:
        lines.append("")
        lines.append("Upcharges:")
        for k, v in non_zero_upcharges.items():
            pct = f"{round(v * 100, 1)}%"
            label = k.replace("_", " ").title() + ":"
            lines.append(f"{label.ljust(col_width)}{pct}")
        lines.append("-" * (col_width * 2))

    # Totals
    lines.append(f"{'Time Used:'.ljust(col_width)}{response_json.get('calculation_time', '')}")

    lines.append(f"{'Standard Quote:'.ljust(col_width)}${response_json['standard_quote']}")
    lines.append(f"{'Combined Upcharge %:'.ljust(col_width)}{response_json['combined_upcharge_percentage']*100}%")
    lines.append(f"{'Upcharge Amount:'.ljust(col_width)}${response_json['upcharge_amount']}")
    lines.append(f"{'TowDynamiq Quote:'.ljust(col_width)}${response_json['todynamiq_quote']}")

    return "\n".join(lines)




def load_json(filename):
    with open(os.path.join("data", filename), "r") as f:
        return json.load(f)


def get_billable_miles(actual_miles: int, dynamic_modifiers: dict) -> int:
    """
    Calculate billable miles using either 'pattern' or 'tiers' mode.
    """
    mode = dynamic_modifiers["bucket_mileage_pricing"]["mode"]

    if mode == "tiers":
        for rng, values in dynamic_modifiers["bucket_mileage_pricing"]["tiers"].items():
            start, end = map(int, rng.split("-"))
            if start <= actual_miles <= end:
                return values["billable_miles"]
        return actual_miles  # fallback if not in any tier

    elif mode == "pattern":
        rules = dynamic_modifiers["bucket_mileage_pricing"]["pattern"]
        # Free range (0–5 miles no charge)
        if actual_miles <= 5:
            return 0

        start = rules["start"]
        step = rules["first_step"]
        cap = start + step - 1

        while cap < rules["max_miles"]:
            if actual_miles <= cap:
                return cap
            step += rules["step_growth"]   # widen the interval
            start = cap + 1
            cap = start + step - 1

        return rules["max_miles"]

    else:
        raise ValueError(f"Unknown mileage mode: {mode}")

@app.route("/")
def home():
    return render_template("home.html")  # still "coming soon"


@app.route("/testquote007")
def testquote007():
    pricing = load_json("pricing.json")
    dynamic_modifiers = load_json("dynamic_modifiers.json")
    cars = load_json("cars.json")
    return render_template("testquote007.html",
                           pricing=pricing,
                           dynamic_modifiers=dynamic_modifiers,
                           cars=cars)


from datetime import datetime

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    tow_type = data.get("tow_type")
    services = data.get("services", [])
    is_accident = data.get("is_accident") == "yes"
    source = data.get("source")
    destination = data.get("destination")

    if not source or not destination:
        return jsonify({"error": "Source and destination are required"}), 400

    try:
        distance_info = get_distance(source, destination)
        g_miles = distance_info["g_miles"]
        distance_text = distance_info["distance_text"]
        # Overwrite with Google's resolved addresses
        resolved_source = distance_info["resolved_origin"]
        resolved_destination = distance_info["resolved_destination"]
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    make = data.get("make")
    model = data.get("model")
    unsafe_location = data.get("unsafe_location")  # dict {road_type, lane}
    weather = data.get("weather")

    pricing = load_json("pricing.json")
    dynamic_modifiers = load_json("dynamic_modifiers.json")
    cars = load_json("cars.json")

    if tow_type not in pricing:
        return jsonify({"error": f"Invalid tow type: {tow_type}"}), 400

    breakdowns = []
    total = 0

    for service in services:
        if service not in pricing[tow_type]:
            return jsonify({"error": f"Invalid service: {service}"}), 400

        config = pricing[tow_type][service]

        hook = config["rate"]
        per_mile = config["mileage"]
        included = config.get("includes", 0)
        print(f"included: {included}")
        if is_accident and "accident" in config:
            hook = config["accident"].get("hook", hook)
            per_mile = config["accident"].get("mileage", per_mile)
            included = config["accident"].get("includes", included)

        # mileage = max(0, get_billable_miles(miles, dynamic_modifiers) - included)
        # mileage_cost = mileage * per_mile
        # subtotal = hook + mileage_cost

        # breakdowns.append({
        #     "service": config["label"],
        #     "hook": hook,
        #     "mileage": mileage,
        #     "per_mile": per_mile,
        #     "mileage_cost": round(mileage_cost, 2),
        #     "includes": included,
        #     # "subtotal": round(subtotal, 2),
        #     "accident_applied": is_accident and "accident" in config
        # })
        # get the global billable miles once (outside loop)
        billable_miles = get_billable_miles(g_miles, dynamic_modifiers)

        # then inside loop use this:
        extra_miles = max(0, billable_miles - included)
        print(extra_miles)
        mileage_cost = round(extra_miles * per_mile, 2)
        subtotal = hook + mileage_cost

        breakdowns.append({
            "service": config["label"],
            "hook": hook,
            "mileage": extra_miles,   # 👈 now reflects per-service miles after included
            "per_mile": per_mile,
            "mileage_cost": mileage_cost,
            "includes": included,
            "accident_applied": is_accident and "accident" in config
        })


        total += subtotal

    # -------------------------
    # ✅ COLLECT ALL UPCHARGES
    # -------------------------
    upcharges = {
        "make_model": 0.0,
        "vehicle_location": 0.0,
        "weather": 0.0,
        "truck_utilization": 0.0,
        "time_of_day": 0.0,
    }

    # --- Car make/model ---
    if make and model:
        make_entry = cars.get(make)
        if make_entry:
            model_entry = make_entry["models"].get(model)
            if model_entry:
                upcharges["make_model"] = model_entry.get("upcharge_percentage", 0.0)

    # --- Vehicle location ---
    if unsafe_location:
        road_type = unsafe_location.get("road_type")
        lane = unsafe_location.get("lane")
        if road_type in dynamic_modifiers["vehicle_location"]:
            road_data = dynamic_modifiers["vehicle_location"][road_type]
            if lane in road_data["lanes"]:
                upcharges["vehicle_location"] = road_data["lanes"][lane].get("upcharge", 0.0)

    # --- Weather ---
    if weather and weather in dynamic_modifiers["weather"]:
        upcharges["weather"] = dynamic_modifiers["weather"][weather].get("upcharge", 0.0)

    # --- Time of day ---
    local_time_str = data.get("local_time")
    tz_offset = data.get("timezone_offset")

    if local_time_str and tz_offset is not None:
        try:
            # Parse as UTC first
            client_time = datetime.fromisoformat(local_time_str.replace("Z", "+00:00"))

            # Adjust using browser's offset (JS getTimezoneOffset gives minutes *behind* UTC)
            offset = timedelta(minutes=-int(tz_offset))
            local_time = client_time + offset

            # keep full datetime for display
            calculation_datetime = local_time # Just for display
            calculation_time = calculation_datetime.strftime("%Y-%m-%d %H:%M:%S")  # Just for display

            now = local_time.time() # for calculation
        except Exception as e:
            print("⚠️ Failed to parse local_time:", local_time_str, tz_offset, e)
            now = datetime.utcnow().time()
    else:
        # Fallback: if frontend didn’t send local time
        now = datetime.utcnow().time()

    for slot, slot_data in dynamic_modifiers.get("time_of_day", {}).items():
        start = datetime.strptime(slot_data["start"], "%H:%M").time()
        end = datetime.strptime(slot_data["end"], "%H:%M").time()
        if start <= now <= end:
            upcharges["time_of_day"] = slot_data.get("upcharge", 0.0)
            break


    # --- Final combined percentage (capped at 0.25) ---
    combined_upcharge = sum(upcharges.values())
    combined_upcharge = min(combined_upcharge, 0.25)

    upcharge_amount = round(total * combined_upcharge, 2)
    final_total = round(total + upcharge_amount, 2)

    # -------------------------
    # ✅ RESPONSE
    # -------------------------
    response = OrderedDict()
    # User input
    response["source"] = source
    response["destination"] = destination
    # Google resolved addresses
    response["source_resolved"] = resolved_source
    response["destination_resolved"] = resolved_destination

    # Distance
    response["distance_miles"] = g_miles
    response["distance_text"] = distance_text

    # Tow info
    response["tow_type"] = tow_type
    response["services"] = breakdowns
    response["calculation_time"] = calculation_time

    # Pricing
    response["standard_quote"] = round(total, 2)
    response["upcharges"] = {k: round(v, 3) for k, v in upcharges.items()}
    response["combined_upcharge_percentage"] = round(combined_upcharge, 3)
    response["upcharge_amount"] = upcharge_amount
    response["todynamiq_quote"] = final_total

    # Breakdown string
    response["breakdown"] = format_breakdown(response)


    return Response(json.dumps(response), mimetype="application/json")


if __name__ == "__main__":
    debug_mode = os.environ.get("debug_mode", "false").lower() == "true"
    port = int(os.environ.get("PORT", 10000))  # use Render's PORT if present, else fallback
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
