from dotenv import load_dotenv
load_dotenv()

import os
import re
from typing import Optional, Dict, Set, List, Any
from datetime import datetime, timedelta

import mysql.connector
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
from jose import JWTError, jwt

# Gemini client
from google import genai

import json
import time

# -------------------------
# Config
# -------------------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "srv1085.hstgr.io")
MYSQL_USER = os.environ.get("MYSQL_USER", "u477873453_std")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "lR0$bUKGV*?b")
MYSQL_DB = os.environ.get("MYSQL_DB", "u477873453_stmic")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
JWT_SECRET = os.environ.get("JWT_SECRET", "change_this_super_secret")
JWT_ALGO = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 240))

# -------------------------
# Init
# -------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = HTTPBearer()

app = FastAPI(title="SchoolData Chatbot API")

# Init Gemini
genai_client = None

# FIX: Updated to "gemini-2.0-flash-exp" to fix 404 errors
GENAI_MODEL = "models/gemini-flash-latest"


if GEMINI_API_KEY:
    try:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"✅ Gemini Client Connected. Using model: {GENAI_MODEL}")
    except Exception as e:
        genai_client = None
        print(f"❌ Error initializing Gemini Client: {e}")
else:
    print("⚠️ Warning: GEMINI_API_KEY is missing in .env file.")

def log_kpi_event(
    event_type: str,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    success: bool = True,
    latency_ms: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
):
    """
    Write a KPI event into kpi_events table.

    Expected DB table:

    CREATE TABLE kpi_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        ts DATETIME NOT NULL,
        user_id INT NULL,
        role VARCHAR(20) NULL,
        event_type VARCHAR(50) NOT NULL,
        success TINYINT(1) NOT NULL,
        latency_ms INT NULL,
        meta_json TEXT NULL
    );
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        meta_json = json.dumps(meta or {}, ensure_ascii=False)

        cur.execute(
            """
            INSERT INTO kpi_events
            (ts, user_id, role, event_type, success, latency_ms, meta_json)
            VALUES (NOW(), %s, %s, %s, %s, %s, %s)
            """,
            (
                int(user_id) if user_id is not None else None,
                role,
                event_type,
                1 if success else 0,
                int(latency_ms) if latency_ms is not None else None,
                meta_json,
            ),
        )
        conn.commit()
    except Exception as e:
        # Don't crash the app because of KPI logging
        print("KPI log error:", e)
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass


# -------------------------
# DB Helpers
# -------------------------
def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, port=MYSQL_PORT, connection_timeout=10
    )

ALLOWED_TABLES = [
    "students", "student_details", "attendance", "fee_payments",
    "academic_marks", "hostel_transport", "medical_info"
]
ALLOWED_TABLES_WITH_TEACHERS = ALLOWED_TABLES + ["teachers"]

def introspect_allowed_columns() -> Dict[str, list]:
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        allowed = {}
        for t in ALLOWED_TABLES_WITH_TEACHERS:
            try:
                cur.execute(f"DESCRIBE `{t}`;")
                allowed[t] = [r[0] for r in cur.fetchall()]
            except:
                allowed[t] = []
        conn.close()
        return allowed
    except Exception as e:
        print("DB Introspection failed:", e)
        return {t: [] for t in ALLOWED_TABLES_WITH_TEACHERS}

ALLOWED_COLUMNS = introspect_allowed_columns()

# -------------------------
# Auth Logic
# -------------------------
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGO)

def decode_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        return None

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ChatRequest(BaseModel):
    message: str

@app.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    start = time.perf_counter()
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute(
            "SELECT id, email, password, name FROM students WHERE email = %s LIMIT 1",
            (data.email,),
        )
        user = cur.fetchone()
        role = "student"

        if not user:
            cur.execute(
                "SELECT id, email, password, name FROM teachers WHERE email = %s LIMIT 1",
                (data.email,),
            )
            user = cur.fetchone()
            role = "teacher"

        if not user or not verify_password(data.password, user["password"]):
            latency_ms = int((time.perf_counter() - start) * 1000)
            # KPI: login failed
            log_kpi_event(
                event_type="login_failed",
                user_id=None,
                role=None,
                success=False,
                latency_ms=latency_ms,
                meta={"email": data.email},
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token(
            {"sub": str(user["id"]), "role": role, "name": user.get("name")}
        )

        latency_ms = int((time.perf_counter() - start) * 1000)
        # KPI: login success
        log_kpi_event(
            event_type="login_success",
            user_id=int(user["id"]),
            role=role,
            success=True,
            latency_ms=latency_ms,
            meta={"email": user["email"]},
        )

        return {"access_token": token, "token_type": "bearer"}

    finally:
        conn.close()


def get_current_user(auth: HTTPAuthorizationCredentials = Depends(oauth2_scheme)):
    token = auth.credentials
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# -------------------------
# AI & Logic
# -------------------------
class ChatSQLHelper:
    def __init__(self, client, model):
        self.client = client
        self.model = model

    def generate_sql(self, nl_query, schema_text, user_context):
        prompt = f"""
        You are a MySQL expert. Analyze the user request.
        
        SCHEMA:
        {schema_text}
        
        CONTEXT:
        {user_context}
        
        INSTRUCTIONS:
        1. If the user is saying "Hi", "Hello", "Thanks", or asking "Who are you?", return EXACTLY the word: NOT_SQL
        2. If the user asks for data (marks, fees, students), return a SINGLE SQL query.
        3. Return ONLY raw text (no markdown, no ```).
        4. Use LOWER(col) LIKE '%val%' for text matching.
        
        User Question: "{nl_query}"
        """
        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            text = resp.text.replace("```sql", "").replace("```", "").strip()
            return text
        except Exception as e:
            return f"ERROR: {str(e)}"

    def generate_human_response(self, nl_query, sql, rows, is_chitchat=False):
        if is_chitchat:
            prompt = f"""
            You are a helpful School Data Assistant.
            User said: "{nl_query}"
            Reply politely and briefly. Tell them you can help with Marks, Attendance, contact details, medical history and Fees.
            """
        else:
            if not rows and "ERROR" not in str(rows):
                 return "I checked the records, but I couldn't find any information matching your request."
            
            data_preview = str(rows[:10])
            prompt = f"""
            You are a School Administrator Assistant.
            User Question: "{nl_query}"
            SQL Used: "{sql}"
            Data Found: {data_preview}
            
            Summarize the data nicely for the user in 2-3 sentences.
            """

        try:
            resp = self.client.models.generate_content(model=self.model, contents=prompt)
            return resp.text.strip()
        except Exception as e:
            return f"I found data but couldn't summarize it. Error: {e}"

chat_helper = ChatSQLHelper(genai_client, GENAI_MODEL)

# -------------------------
# Chat Endpoint
# -------------------------
@app.post("/chat")
def chat_endpoint(req: ChatRequest, user=Depends(get_current_user)):
    start = time.perf_counter()

    if not genai_client:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_kpi_event(
            event_type="chat_error",
            user_id=None,
            role=None,
            success=False,
            latency_ms=latency_ms,
            meta={"reason": "no_genai_client"},
        )
        return {
            "summary": "Critical Error: AI Client is not initialized. Check backend terminal.",
            "results": [],
        }

    user_id = int(user.get("sub") or user.get("id"))
    role = user.get("role", "student")

    schema_text = "\n".join(
        [f"- {t}: {ALLOWED_COLUMNS.get(t)}" for t in ALLOWED_TABLES_WITH_TEACHERS]
    )
    if role == "student":
        context = f"User is Student (ID: {user_id}). MUST filter by `student_id = {user_id}`."
    else:
        context = "User is Teacher."

    # 2. Generate SQL (or NOT_SQL / ERROR)
    sql_or_response = chat_helper.generate_sql(req.message, schema_text, context)

    # Case A: AI Error
    if sql_or_response.startswith("ERROR:"):
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_kpi_event(
            event_type="chat_ai_error",
            user_id=user_id,
            role=role,
            success=False,
            latency_ms=latency_ms,
            meta={"error": sql_or_response, "message": req.message},
        )
        return {"summary": f"AI Error: {sql_or_response}", "results": []}

    # Case B: Chit-Chat
    if sql_or_response == "NOT_SQL":
        summary = chat_helper.generate_human_response(
            req.message, "", [], is_chitchat=True
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_kpi_event(
            event_type="chat_chitchat",
            user_id=user_id,
            role=role,
            success=True,
            latency_ms=latency_ms,
            meta={"message": req.message},
        )
        return {"summary": summary, "results": []}

    # Case C: Real SQL
    sql = sql_or_response

    # ---------------------------------------------------------
    # 3. STRONG STUDENT PRIVACY ENFORCEMENT
    # ---------------------------------------------------------
    import re

    def extract_tables(sql):
        """
        Extract table names from SQL query safely.
        Returns a set of table names in lowercase.
        """

        sql = sql.lower()

        # Match FROM <table> OR JOIN <table>
        matches = re.findall(r"(from|join)\s+([a-zA-Z0-9_]+)", sql)

        tables = set()
        for m in matches:
            tables.add(m[1])

        return tables

    tables = extract_tables(sql)
    lower_sql = sql.lower()

    if role == "student":

        # 3A — Completely forbid access to teachers table
        if "teachers" in tables:
            return {
                "summary": "Access denied. Students cannot view teacher data.",
                "results": [],
                "sql": None
            }

        # 3B — Forbid access to ALL other students
        # If the query touches the students table, enforce students.id = current_user
        if "students" in tables:
            if f"students.id = {user_id}" not in lower_sql and f"students.id={user_id}" not in lower_sql:
                return {
                    "summary": "Access denied. Students cannot view other students’ information.",
                    "results": [],
                    "sql": None
                }

        # 3C — For ANY table that uses student_id, enforce their own ID
        needs_filter = False

        # List of tables with student_id column
        student_related_tables = {
            "attendance",
            "fee_payments",
            "academic_marks",
            "hostel_transport",
            "medical_info",
            "student_details",
        }

        for t in tables:
            if t in student_related_tables:
                needs_filter = True

        # If query involves student data but does NOT filter by their own ID, force block
        if needs_filter:
            if f"student_id = {user_id}" not in lower_sql and f"student_id={user_id}" not in lower_sql:
                return {
                    "summary": "Access denied. Students cannot view other students’ records.",
                    "results": [],
                    "sql": None
                }


    # 4. Execute
    rows = []
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(sql)
        rows = cur.fetchall()
        conn.close()
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log_kpi_event(
            event_type="chat_db_error",
            user_id=user_id,
            role=role,
            success=False,
            latency_ms=latency_ms,
            meta={"error": str(e), "sql": sql, "message": req.message},
        )
        return {"summary": f"Database Error: {e}", "results": []}

    # 5. Summarize
    summary = chat_helper.generate_human_response(req.message, sql, rows)

    latency_ms = int((time.perf_counter() - start) * 1000)
    log_kpi_event(
        event_type="chat_success",
        user_id=user_id,
        role=role,
        success=True,
        latency_ms=latency_ms,
        meta={
            "message": req.message,
            "sql": sql,
            "row_count": len(rows),
        },
    )

    return {
        "summary": summary,
        "results": rows[:50],
        "sql": sql,
    }

@app.get("/me")
def me(user=Depends(get_current_user)):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(dictionary=True)

        user_id = int(user["sub"])   # ← FIX: get ID from JWT

        if user["role"] == "student":
            cur.execute("SELECT id, email, name FROM students WHERE id = %s LIMIT 1", (user_id,))
        else:
            cur.execute("SELECT id, email, name FROM teachers WHERE id = %s LIMIT 1", (user_id,))

        db_user = cur.fetchone()
        cur.close()

        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": db_user["id"],
            "email": db_user["email"],
            "role": user["role"],
            "name": db_user.get("name")
        }

    finally:
        if conn:
            conn.close()

# -------------------------
# KPI Summary Endpoints
# -------------------------
@app.get("/kpi/summary")
def kpi_summary(user=Depends(get_current_user)):
    """
    Returns high-level KPIs for teachers (admin).
    """
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Teacher only")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Total chat queries
        cur.execute(
            """
            SELECT
              COUNT(*) AS total_queries,
              SUM(CASE WHEN event_type = 'chat_success' AND is_success = 1 THEN 1 ELSE 0 END) AS success_queries,
              AVG(CASE WHEN event_type LIKE 'chat_%' AND response_time_ms IS NOT NULL THEN response_time_ms END) AS avg_response_ms,
              SUM(CASE WHEN event_type = 'chat_error' THEN 1 ELSE 0 END) AS error_events
            FROM kpi_events
            """
        )
        row = cur.fetchone() or {}

        total_queries = row["total_queries"] or 0
        success_queries = row["success_queries"] or 0
        error_events = row["error_events"] or 0
        avg_response_ms = row["avg_response_ms"]

        # Login success rate
        cur.execute(
            """
            SELECT
              COUNT(*) AS total_logins,
              SUM(CASE WHEN event_type = 'login_success' THEN 1 ELSE 0 END) AS success_logins
            FROM kpi_events
            WHERE event_type LIKE 'login_%'
            """
        )
        log_row = cur.fetchone() or {}
        total_logins = log_row["total_logins"] or 0
        success_logins = log_row["success_logins"] or 0

        login_success_rate = (
            round(success_logins * 100.0 / total_logins, 2) if total_logins > 0 else None
        )
        query_success_rate = (
            round(success_queries * 100.0 / total_queries, 2)
            if total_queries > 0
            else None
        )
        api_error_rate = (
            round(error_events * 100.0 / total_queries, 2)
            if total_queries > 0
            else None
        )

        return {
            "total_queries": total_queries,
            "chat_success_rate_percent": query_success_rate,
            "avg_chat_response_ms": avg_response_ms,
            "api_error_rate_percent": api_error_rate,
            "total_logins": total_logins,
            "login_success_rate_percent": login_success_rate,
        }

    finally:
        cur.close()
        conn.close()
@app.get("/kpi/daily-usage")
def kpi_daily_usage(user=Depends(get_current_user)):
    """
    Returns per-day chat usage (for charts on the dashboard).
    """
    if user.get("role") != "teacher":
        raise HTTPException(status_code=403, detail="Teacher only")

    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT
              DATE(created_at) AS day,
              SUM(CASE WHEN event_type = 'chat_success' THEN 1 ELSE 0 END) AS successful_chats,
              SUM(CASE WHEN event_type = 'chat_error' THEN 1 ELSE 0 END) AS chat_errors
            FROM kpi_events
            WHERE event_type LIKE 'chat_%'
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """
        )
        rows = cur.fetchall()
        return rows
    finally:
        cur.close()
        conn.close()
