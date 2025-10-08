from app import app, db, User
from werkzeug.security import generate_password_hash

# --- Fill in details for the new user ---
username = "nathanfoster"
password = "Nathan@5678"
role = "admin3"

# --- Hash the password ---
hashed_pw = generate_password_hash(password)

# --- Create and save the user ---
new_user = User(username=username, password_hash=hashed_pw, role=role)

# 🔑 This creates a temporary Flask app context so db.session works
with app.app_context():
    db.session.add(new_user)
    db.session.commit()
    print(f"✅ Created user '{username}' with role '{role}'")
