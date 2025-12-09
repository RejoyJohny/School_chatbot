# flask_frontend/app.py

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from dotenv import load_dotenv
import os
import requests

load_dotenv()
import mysql.connector



# Load DB config from .env
MYSQL_HOST = os.environ.get("MYSQL_HOST", "srv1085.hstgr.io")
MYSQL_USER = os.environ.get("MYSQL_USER", "u477873453_std")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "lR0$bUKGV*?b")
MYSQL_DB = os.environ.get("MYSQL_DB", "u477873453_stmic")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

def get_db_connection():
    """Create database connection for KPI dashboard."""
    return mysql.connector.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        port=MYSQL_PORT
    )


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


# 1. THE PAGE ROUTE (Renders the HTML)
@app.route("/dashboard")
def kpi_page():
    if not is_logged_in() or session.get("user_role") != "teacher":
        return redirect(url_for("chat"))
    # Make sure your HTML file is named 'kpi_dashboard.html' inside /templates
    return render_template("kpi_dashboard.html") 

# 2. THE API ROUTE (Returns the Data)
@app.route("/api/kpi-data")
def kpi_data():
    if not is_logged_in() or session.get("user_role") != "teacher":
        return jsonify({"error": "Unauthorized"}), 403

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    # ---------- A. OVERALL STATS (chat + login) ----------
    cur.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN event_type LIKE 'chat_%' THEN 1 ELSE 0 END), 0) AS total_queries,
            COALESCE(SUM(CASE WHEN event_type = 'chat_success' THEN 1 ELSE 0 END), 0) AS success_count,
            COALESCE(SUM(CASE WHEN event_type IN ('chat_error','chat_ai_error','chat_db_error')
                              THEN 1 ELSE 0 END), 0) AS error_count,
            COALESCE(SUM(CASE WHEN event_type = 'login_success' THEN 1 ELSE 0 END), 0) AS login_success,
            COALESCE(SUM(CASE WHEN event_type = 'login_failed' THEN 1 ELSE 0 END), 0) AS login_failed,
            COALESCE(AVG(CASE WHEN event_type LIKE 'chat_%' THEN latency_ms END), 0) AS avg_response_time
        FROM kpi_events;
    """)
    stats = cur.fetchone()

    # ---------- B. DAILY USAGE TREND (all chat events) ----------
    cur.execute("""
        SELECT DATE(ts) AS day, COUNT(*) AS count
        FROM kpi_events
        WHERE event_type LIKE 'chat_%'
        GROUP BY DATE(ts)
        ORDER BY day ASC;
    """)
    usage_trend = cur.fetchall()

    # ---------- C. TEACHER USAGE (top 5) ----------
    cur.execute("""
        SELECT user_id, COUNT(*) AS count
        FROM kpi_events
        WHERE role = 'teacher' AND event_type LIKE 'chat_%'
        GROUP BY user_id
        ORDER BY count DESC
        LIMIT 5;
    """)
    teacher_usage = cur.fetchall()

    # ---------- D. STUDENT LOGIN TREND ----------
    cur.execute("""
        SELECT DATE(ts) AS day, COUNT(*) AS count
        FROM kpi_events
        WHERE role = 'student' AND event_type = 'login_success'
        GROUP BY DATE(ts)
        ORDER BY day ASC;
    """)
    student_login_trend = cur.fetchall()

    # ---------- E. SYSTEM UPTIME / ACTIVITY PER DAY ----------
    # (proxy: number of events per day – higher = more active/available)
    cur.execute("""
        SELECT DATE(ts) AS day, COUNT(*) AS count
        FROM kpi_events
        GROUP BY DATE(ts)
        ORDER BY day ASC;
    """)
    uptime_trend = cur.fetchall()

    conn.close()

    return jsonify({
        "stats": stats,
        "usage_trend": usage_trend,
        "teacher_usage": teacher_usage,
        "student_login_trend": student_login_trend,
        "uptime_trend": uptime_trend,
    })


if __name__ == "__main__":
    # Run Flask frontend on port 5000
    app.run(host="127.0.0.1", port=5000, debug=True)
