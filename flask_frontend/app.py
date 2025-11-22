# flask_frontend/app.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from dotenv import load_dotenv
import os
import requests

load_dotenv()


app = Flask(__name__, static_folder='static', template_folder='templates')

# Secret key for Flask sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev_secret_change_me")

# URL of your FastAPI backend
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://127.0.0.1:8000")


# -------------------------
# Helpers
# -------------------------
def is_logged_in():
    return "access_token" in session


def get_auth_headers():
    token = session.get("access_token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


# -------------------------
# Routes
# -------------------------
@app.route("/")
def index():
    if is_logged_in():
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    # POST: handle login form
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("login"))

    try:
        resp = requests.post(
            f"{BACKEND_BASE_URL}/login",
            json={"email": email, "password": password},
            timeout=10
        )
    except Exception as e:
        flash(f"Could not reach backend API: {e}", "error")
        return redirect(url_for("login"))

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "Login failed")
        except Exception:
            detail = "Login failed"
        flash(f"Login error: {detail}", "error")
        return redirect(url_for("login"))

    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        flash("Backend did not return an access token.", "error")
        return redirect(url_for("login"))

    # Fetch user info from /me
    try:
        me_resp = requests.get(
            f"{BACKEND_BASE_URL}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        if me_resp.status_code != 200:
            flash("Login succeeded but failed to fetch user profile.", "error")
            return redirect(url_for("login"))
        me_data = me_resp.json()
    except Exception as e:
        flash(f"Error fetching user profile: {e}", "error")
        return redirect(url_for("login"))

    # Save in session
    session["access_token"] = access_token
    session["user_email"] = me_data.get("email")
    session["user_name"] = me_data.get("name", "User")
    session["user_role"] = me_data.get("role", "student")

    return redirect(url_for("chat"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/chat")
def chat():
    if not is_logged_in():
        return redirect(url_for("login"))

    return render_template(
        "chat.html",
        user_name=session.get("user_name", "User"),
        user_role=session.get("user_role", "student"),
        user_email=session.get("user_email", "")
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Frontend -> Flask -> FastAPI /chat
    """
    if not is_logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    try:
        resp = requests.post(
            f"{BACKEND_BASE_URL}/chat",
            json={"message": message, "request_sql": False},
            headers=get_auth_headers(),
            timeout=30
        )
    except Exception as e:
        return jsonify({"error": f"Backend error: {e}"}), 500

    if resp.status_code != 200:
        try:
            detail = resp.json().get("detail", "Chat error")
        except Exception:
            detail = "Chat error"
        return jsonify({"error": detail}), resp.status_code

    chat_data = resp.json()
    return jsonify(chat_data)


if __name__ == "__main__":
    # Run Flask frontend on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
