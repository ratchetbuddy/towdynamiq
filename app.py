from flask import Flask, render_template, request, jsonify
import os
import json

app = Flask(__name__)

# helper function to load pricing.json
def load_pricing():
    with open(os.path.join("data", "pricing.json"), "r") as f:
        return json.load(f)

# helper function to load dynamic_modifiers.json
def load_modifiers():
    with open(os.path.join("data", "dynamic_modifiers.json"), "r") as f:
        return json.load(f)

# helper function to load cars.json
def load_cars():
    with open(os.path.join("data", "cars.json"), "r") as f:
        return json.load(f)

@app.route("/")
def home():
    return render_template("home.html")  # still "coming soon"


@app.route("/testquote007")
def testquote007():
    pricing = load_pricing()
    dynamic_modifiers = load_modifiers()
    cars = load_cars()
    return render_template("testquote007.html",
                           pricing=pricing,
                           dynamic_modifiers=dynamic_modifiers,
                           cars=cars)



@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    tow_type = data.get("tow_type")
    service_type = data.get("service")
    miles = float(data.get("distance", 0))

    pricing = load_pricing()

    if tow_type not in pricing or service_type not in pricing[tow_type]:
        return jsonify({"error": "Invalid duty or service type"}), 400

    config = pricing[tow_type][service_type]

    hook = config["rate"]
    per_mile = config["mileage"]
    included = config.get("includes", 0)

    extra_miles = max(0, miles - included)
    mileage_cost = extra_miles * per_mile
    total = hook + mileage_cost

    col_width = 25
    breakdown = (
        f"{'Tow Type:'.ljust(col_width)}{tow_type}\n"
        f"{'Service:'.ljust(col_width)}{config['label']}\n"
        f"{'Hook Fee:'.ljust(col_width)}${hook}\n"
        f"{'Miles Charged:'.ljust(col_width)}{extra_miles} @ ${per_mile}/mile = ${mileage_cost}\n"
        f"{'Included Miles:'.ljust(col_width)}{included}\n"
        f"{'-'*15}{'-'*15}\n"
        f"{'Total:'.ljust(col_width)}${total}"
    )

    return jsonify({
        "tow_type": tow_type,
        "service": config["label"],
        "hook": hook,
        "extra_miles": extra_miles,
        "per_mile": per_mile,
        "mileage_cost": round(mileage_cost, 2),
        "includes": included,
        "total": round(total, 2),
        "breakdown": breakdown
    })

if __name__ == '__main__':
    debug_mode = os.environ.get("debug_mode", "false").lower() == "true"
    app.run(host="0.0.0.0", port=10000, debug=debug_mode)
