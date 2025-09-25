from flask import Flask, render_template, request, jsonify, Response
import os
import json
from collections import OrderedDict

app = Flask(__name__)

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


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    tow_type = data.get("tow_type")
    services = data.get("services", [])
    miles = float(data.get("distance", 0))
    is_accident = data.get("is_accident") == "yes"  # True/False

    pricing = load_json("pricing.json")
    dynamic_modifiers = load_json("dynamic_modifiers.json")

    if tow_type not in pricing:
        return jsonify({"error": f"Invalid tow type: {tow_type}"}), 400

    breakdowns = []
    total = 0

    for service in services:
        if service not in pricing[tow_type]:
            return jsonify({"error": f"Invalid service: {service}"}), 400

        config = pricing[tow_type][service]

        # ----- Base values -----
        hook = config["rate"]
        per_mile = config["mileage"]
        included = config.get("includes", 0)

        # ----- Accident overrides (if present) -----
        if is_accident and "accident" in config:
            hook = config["accident"].get("hook", hook)
            per_mile = config["accident"].get("mileage", per_mile)
            included = config["accident"].get("includes", included)

        # ----- Calculate -----
        mileage = max(0, get_billable_miles(miles,dynamic_modifiers) - included)
        #Check with team about this calculation of mileage bucket vs included deduction?

        mileage_cost = mileage * per_mile
        subtotal = hook + mileage_cost

        breakdowns.append({
            "service": config["label"],
            "hook": hook,
            "mileage": mileage,
            "per_mile": per_mile,
            "mileage_cost": round(mileage_cost, 2),
            "includes": included,
            "subtotal": round(subtotal, 2),
            "accident_applied": is_accident and "accident" in config
        })

        total += subtotal

    response = OrderedDict()
    response["tow_type"] = tow_type
    response["services"] = breakdowns
    response["total"] = round(total, 2)

    return Response(json.dumps(response), mimetype="application/json")




if __name__ == "__main__":
    debug_mode = os.environ.get("debug_mode", "false").lower() == "true"
    port = int(os.environ.get("PORT", 10000))  # use Render's PORT if present, else fallback
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
