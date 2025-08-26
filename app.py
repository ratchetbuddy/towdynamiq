from flask import Flask, render_template, request, jsonify
import os

app = Flask(__name__)

# pricing map with display labels
pricing = {
    "Light Duty": {
        "hook": {
            "label": "Hook",
            "rate": 125,      # flat fee for hookup
            "mileage": 5,     # per-mile rate after included miles
            "includes": 0     # free miles included
        },
        "connex": {
            "label": "Connex",
            "rate": 250,
            "mileage": 5,
            "includes": 0
        }
    },
    "Medium Duty": {
        "hook": {
            "label": "Hook",
            "rate": 150,
            "mileage": 10,
            "includes": 0
        }
    },
    "Heavy Duty": {
        "hook": {
            "label": "Hook",
            "rate": 175,
            "mileage": 15,
            "includes": 5
        }
    }
}


@app.route("/")
def home():
    return render_template("home.html")  # still "coming soon"


@app.route("/quote")
def quote():
    return render_template("quote.html")


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()
    tow_type = data.get("tow_type")
    service_type = data.get("service")
    miles = float(data.get("distance", 0))

    if tow_type not in pricing or service_type not in pricing[tow_type]:
        return jsonify({"error": "Invalid duty or service type"}), 400

    config = pricing[tow_type][service_type]

    hook = config["rate"]
    per_mile = config["mileage"]
    included = config.get("includes", 0)

    extra_miles = max(0, miles - included)
    mileage_cost = extra_miles * per_mile
    total = hook + mileage_cost

    # format output like a receipt
    col_width = 22  # width for labels
    breakdown = (
        f"{'Duty:'.ljust(col_width)}{tow_type}\n"
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
        "breakdown": breakdown   # 👈 send preformatted text
    })

if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=10000, debug=debug_mode)
