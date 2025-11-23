📚 SchoolData Chatbot – README
🚀 Overview

SchoolData Chatbot is an AI-powered system that allows students and teachers to query school data (attendance, marks, fees, transport, medical info, etc.) using natural language.
It uses:

FastAPI (Backend + AI + SQL engine)

Flask (Frontend UI)

MySQL (Hostinger server)

Gemini API (AI → SQL + Chat responses)

📁 Project Structure
/backend
    main.py
    .env
    requirements.txt

/frontend
    app.py
    templates/
    static/

⚙️ Requirements
Install Python packages:

Backend:

pip install fastapi uvicorn python-dotenv mysql-connector-python passlib[bcrypt] python-jose google-genai


Frontend:

pip install flask requests python-dotenv

🖥️ 1. Setup Environment Variables

Create a file:

backend/.env


Add:

MYSQL_HOST=srvXXXX.hstgr.io
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=your_database_name
MYSQL_PORT=3306

GEMINI_API_KEY=YOUR_API_KEY_HERE
JWT_SECRET=super_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=240


💡 You will find your Hostinger database credentials under:
hPanel → Databases → MySQL Databases

🗄️ 2. Hostinger Database Configuration

Your database must include these tables (case-sensitive):

students

teachers

attendance

fee_payments

academic_marks

hostel_transport

medical_info

student_details

Each table must contain student_id or id so filtering works.

🏃‍♂️ 3. Running the Backend (FastAPI)

Open terminal inside /backend:

cd backend
uvicorn main:app --reload


Backend starts at:

http://127.0.0.1:8000


API docs:

http://127.0.0.1:8000/docs

🧪 Test Backend Endpoints
Login
POST http://127.0.0.1:8000/login


JSON:

{
  "email": "teacher1@example.com",
  "password": "your_password"
}

Test token:
GET http://127.0.0.1:8000/me
Authorization: Bearer <token_here>

Chat:
POST http://127.0.0.1:8000/chat
Authorization: Bearer <token>
{
  "message": "show all students with pending fees"
}

🖥️ 4. Running the Frontend (Flask)

Open terminal:

cd frontend
python app.py


Frontend URL:

http://127.0.0.1:5000

🔗 Frontend → Backend Connection

The frontend calls backend using:

BACKEND_URL = "http://127.0.0.1:8000"


If backend runs on a different system (LAN):

Example:

Backend PC IP:

192.168.1.12


Update frontend .env:

BACKEND_URL=http://192.168.1.12:8000

🌍 Hostinger → Local System Connection (Important)

Your backend does NOT run on Hostinger, only MySQL is remote.

Your backend always connects like this:

host = "srvXXXX.hstgr.io"
user = "uXXXX"
password = "****"
database = "uXXXX_db"
port = 3306

🔒 JWT Auth Summary

Users login with /login

Receive access_token

All /chat and /me requests must include:

Authorization: Bearer <token>

🧠 AI Model Used

Gemini Flash:

models/gemini-flash-latest


Configured in backend:

GENAI_MODEL = "models/gemini-flash-latest"

🧪 Sample Queries for Testing
show my attendance
what is my name
show all students with pending fees
show my marks in semester 1


Students get only their data, teachers get full access.

🛠️ Future Improvements

Dockerized backend & frontend

Multi-language chatbot support

Student-only dashboard

Teacher analytics view
