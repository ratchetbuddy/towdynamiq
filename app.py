from flask import Flask, render_template, request, jsonify, Response, session, redirect, url_for, render_template_string, flash
import os, math, json
from collections import OrderedDict
from datetime import datetime, timezone, timedelta   # ✅ add timedelta here
from flask_sqlalchemy import SQLAlchemy
from helper.functions import (
    get_distance,
    load_json,
    get_billable_miles,
    evaluate_condition,
    format_breakdown,
    get_max_upcharge_cap,
    PRICING_CALCULATORS,
    login_required,
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps


# -------------------------
# 1️⃣  Initialize Flask app
# -------------------------
app = Flask(__name__)


app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_default_key")

app.permanent_session_lifetime = timedelta(minutes=30)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            # redirect to login if user not logged in
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------
# 2️⃣  Neon DB connection
# -------------------------

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------------
# ✅ Session timeout (auto logout)
# -------------------------
@app.before_request
def session_timeout_check():
    session.permanent = True

    # Skip static/login/logout
    if request.endpoint in ["static", "login", "logout", "calculate"]:
        return

    if "user" in session:
        now = datetime.now(timezone.utc).timestamp()  # store as float seconds since epoch
        last_activity = session.get("last_activity")
        timeout_seconds = app.permanent_session_lifetime.total_seconds()

        if last_activity:
            elapsed = now - float(last_activity)
            print(f"⏱ Elapsed: {elapsed:.2f}s / Timeout: {timeout_seconds:.2f}s")

            if elapsed > timeout_seconds:
                flash("You have been logged out due to inactivity.", "warning")
                session.pop("user", None)
                session.pop("role", None)
                session.pop("last_activity", None)
                return redirect(url_for("login"))

        # ✅ Always update (this guarantees persistence)
        session["last_activity"] = now



@app.route("/")
def home():
    return render_template("home.html")  # still "coming soon"

# -------------------------
# 3️⃣  User model
# -------------------------
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")

    def __repr__(self):
        return f"<User {self.username}>"


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            error = "❌ Invalid username or password."
        else:
            # ✅ Save user session
            session["user"] = user.username
            session["role"] = user.role
            return redirect(url_for("testquote007"))

    return render_template("login.html", year=datetime.now().year, error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("role", None)
    return redirect(url_for("login"))  # or any existing route in your app


@app.route("/testquote007")
@login_required  # ✅ protects this route
def testquote007():
    pricing = load_json("pricing.json")
    dynamic_modifiers = load_json("dynamic_modifiers.json")
    cars = load_json("make_model_modifiers.json")
    return render_template("testquote007.html",
                           pricing=pricing,
                           dynamic_modifiers=dynamic_modifiers,
                           cars=cars)



@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.get_json()

    tow_type = data.get("tow_type")
    services = data.get("services", [])
    is_accident = data.get("is_accident") == "yes"
    source = data.get("source")
    destination = data.get("destination")
    # Extra service-specific inputs from frontend
    window_film_entries = data.get("window_film", {})  # default to {} if missing
    side_window = window_film_entries.get("side_window", 0)
    front_or_back_window = window_film_entries.get("front_or_back_window", 0)
    skid_steer_entries = data.get("skid_steer")
    skid_steer_hours = skid_steer_entries.get("hours",0)

    if not source or not destination:
        return jsonify({"error": "Source and destination are required"}), 400

    try:
        distance_info = get_distance(source, destination)
        g_miles_actual = distance_info["g_miles"]
        g_miles = math.ceil(g_miles_actual)
        distance_text = f"{g_miles} mi"
        distance_text_actual = f"{g_miles_actual} mi"
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
    cars = load_json("make_model_modifiers.json")

    if tow_type not in pricing:
        return jsonify({"error": f"Invalid tow type: {tow_type}"}), 400

    breakdowns = []
    standard_total = 0   # before upcharges
    todynamiq_total = 0  # after upcharges


    for service in services:
        if service not in pricing[tow_type]:
            return jsonify({"error": f"Invalid service: {service}"}), 400

        config = pricing[tow_type][service]
        pricing_type = config.get("pricing_type", "flat")

        # -------------------------
        # 1. Apply addon/accident overrides
        # -------------------------
        base_rate = config.get("base_rate", 0)

        # addon rules (override base_rate if condition is true)
        for rule in config.get("rules", []):
            if evaluate_condition(rule["condition"], services):
                base_rate = rule["addon_rate"]
                break

        # accident override
        if is_accident and "accident" in config:
            base_rate = config["accident"].get("hook", base_rate)

        # -------------------------
        # 2. Build inputs for calculators
        # -------------------------
        bucket_miles = get_billable_miles(g_miles, dynamic_modifiers)
        inputs = {"miles": bucket_miles}

        # Window Film → capture both side and front/back counts
        if service == "window_film":
            inputs["side_window"] = side_window
            inputs["front_or_back_window"] = front_or_back_window


        # Skid Steer → capture hours (convert to minutes for time-based calc)
        elif service.startswith("skid_steer"):
            inputs["unit_type"] = "hours"
            inputs["count"] = skid_steer_hours
            inputs["duration_minutes"] = int(skid_steer_hours) * 60


        # -------------------------
        # 3. Dispatch to calculator (bucket miles calc)
        # -------------------------
        if pricing_type in PRICING_CALCULATORS:
            service_cfg = dict(config)
            service_cfg["base_rate"] = base_rate
            calc_result = PRICING_CALCULATORS[pricing_type](service_cfg, inputs)
            bucket_subtotal = calc_result["subtotal"]
        else:
            calc_result = {"subtotal": base_rate}
            bucket_subtotal = base_rate

        # -------------------------
        # 3b. Calculate "standard" subtotal (rounded miles)
        # -------------------------
        if pricing_type == "flat":
            actual_rounded = g_miles  # already ceil’d above
            includes = config.get("includes", 0)
            per_mile = config.get("mileage", 0)

            rounded_miles_charged = max(0, actual_rounded - includes)
            mileage_cost_rounded = rounded_miles_charged * per_mile
            standard_subtotal = base_rate + mileage_cost_rounded
        else:
            standard_subtotal = bucket_subtotal


        # -------------------------
        # 4. Apply per-service modifiers
        # -------------------------
        service_upcharges = {}
        combined_mod_pct = 0.0

        for mod_name, enabled in config.get("modifiers", {}).items():
            if not enabled:
                continue

            value = 0.0
            if mod_name == "make_model" and make and model:
                make_entry = cars.get(make)
                if make_entry:
                    model_entry = make_entry["models"].get(model)
                    if model_entry:
                        value = model_entry.get("upcharge_percentage", 0.0)

            elif mod_name == "vehicle_location" and unsafe_location:
                road_type = unsafe_location.get("road_type")
                lane = unsafe_location.get("lane")
                if road_type in dynamic_modifiers["vehicle_location"]:
                    road_data = dynamic_modifiers["vehicle_location"][road_type]
                    if lane in road_data["lanes"]:
                        value = road_data["lanes"][lane].get("upcharge", 0.0)

            elif mod_name == "weather" and weather:
                if weather in dynamic_modifiers["weather"]:
                    value = dynamic_modifiers["weather"][weather].get("upcharge", 0.0)

            elif mod_name == "time_of_day":
                now = datetime.now(timezone.utc).time()
                local_time_str = data.get("local_time")
                tz_offset = data.get("timezone_offset")
                if local_time_str and tz_offset is not None:
                    try:
                        client_time = datetime.fromisoformat(local_time_str.replace("Z", "+00:00"))
                        offset = timedelta(minutes=-int(tz_offset))
                        now = (client_time + offset).time()
                    except:
                        pass

                for slot, slot_data in dynamic_modifiers.get("time_of_day", {}).items():
                    start = datetime.strptime(slot_data["start"], "%H:%M").time()
                    end = datetime.strptime(slot_data["end"], "%H:%M").time()
                    if start <= now <= end:
                        value = slot_data.get("upcharge", 0.0)
                        break

            elif mod_name == "truck_utilization":
                value = dynamic_modifiers.get("truck_utilization", {}).get("upcharge", 0.0)

            # accumulate
            service_upcharges[mod_name] = value
            combined_mod_pct += value

        # -------------------------
        # Dynamic cap based on subtotal bands
        # -------------------------
        max_cap = get_max_upcharge_cap(standard_subtotal, dynamic_modifiers["subtotal_upcharge_bands"])
        combined_mod_pct = min(combined_mod_pct, max_cap)

        upcharge_amount = round(standard_subtotal * combined_mod_pct, 2)

        # -------------------------
        # 5. Final amounts
        # -------------------------
        mileage_upcharge = bucket_subtotal - standard_subtotal
        service_total = round(standard_subtotal + mileage_upcharge + upcharge_amount, 2)

        breakdowns.append({
            "service": config["label"],
            "pricing_type": pricing_type,
            "standard_quote": round(standard_subtotal, 2),
            "calc_details": calc_result,
            "upcharges": service_upcharges,
            "combined_upcharge_pct": round(combined_mod_pct, 3),
            "upcharge_amount": upcharge_amount,
            "mileage_upcharge": mileage_upcharge,
            "todynamiq_quote": service_total
        })

        standard_total += standard_subtotal
        todynamiq_total += service_total
        overall_pct_chng = (todynamiq_total-standard_total)/todynamiq_total * 100


    # -------------------------
    # Time of calculation (client local time if provided)
    # -------------------------
    local_time_str = data.get("local_time")
    tz_offset = data.get("timezone_offset")

    try:
        if local_time_str and tz_offset is not None:
            client_time = datetime.fromisoformat(local_time_str.replace("Z", "+00:00"))
            offset = timedelta(minutes=-int(tz_offset))  # JS offset is minutes *behind* UTC
            local_time = client_time + offset
            calculation_time = local_time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            calculation_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        print("⚠️ Failed to set calculation_time:", local_time_str, tz_offset, e)
        calculation_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

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
    response["distance_miles"] = g_miles          # Rounded miles
    response["bucket_miles"] = bucket_miles       # True billable miles
    response["distance_text"] = distance_text

    # Tow info
    response["tow_type"] = tow_type
    response["services"] = breakdowns
    response["calculation_time"] = calculation_time
    response["distance_text_actual"] = distance_text_actual
    

    # Pricing
    response["standard_quote"] = round(standard_total, 2)   # 👈 before modifiers
    response["overall_pct_chng"] = round(overall_pct_chng, 2)   # 👈 before modifiers
    response["todynamiq_quote"] = round(todynamiq_total, 2) # 👈 after modifiers


    # Breakdown string
    response["breakdown"] = format_breakdown(response)

    response["window_film"] = window_film_entries
    response["skid_steer"] = skid_steer_entries



    return Response(json.dumps(response), mimetype="application/json")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # ensures the users table exists in Neon
        print("✅ Verified: users table exists in Neon.")    
        
    debug_mode = os.environ.get("debug_mode", "false").lower() == "true"
    port = int(os.environ.get("PORT", 10000))  # use Render's PORT if present, else fallback
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
