Absolutely — here is a **clean GitHub README format** with **clear titles, subtitles, bullet points, and perfect Markdown structure**.
You can paste this directly into GitHub and everything will render beautifully. 🚀🔥

---

# 📚 **SchoolData Chatbot**

An AI-powered system that allows **students and teachers** to query school information using **natural language**.

---

## 🧩 **Tech Stack**

* **FastAPI** – Backend + AI + SQL Engine
* **Flask** – Frontend UI
* **MySQL (Hostinger)** – Remote database
* **Gemini API** – Converts natural language → SQL

---

# 📁 **Project Structure**

```
/backend
    main.py
    .env
    requirements.txt

/frontend
    app.py
    templates/
    static/
```

---

# ⚙️ **Requirements**

## **Backend Packages**

* fastapi
* uvicorn
* python-dotenv
* mysql-connector-python
* passlib[bcrypt]
* python-jose
* google-genai

Install:

```bash
pip install fastapi uvicorn python-dotenv mysql-connector-python passlib[bcrypt] python-jose google-genai
```

## **Frontend Packages**

* flask
* requests
* python-dotenv

Install:

```bash
pip install flask requests python-dotenv
```

---

# 🖥️ **1. Environment Setup**

## **Create `.env` file inside `/backend`**

```
MYSQL_HOST=srvXXXX.hstgr.io
MYSQL_USER=your_mysql_username
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=your_database_name
MYSQL_PORT=3306

GEMINI_API_KEY=YOUR_API_KEY_HERE
JWT_SECRET=super_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=240
```

### ⭐ Hostinger credentials are found here:

* **hPanel → Databases → MySQL Databases**

---

# 🗄️ **2. Hostinger Database Setup**

Your MySQL database must contain the following tables:

* students
* teachers
* attendance
* fee_payments
* academic_marks
* hostel_transport
* medical_info
* student_details

### ⚠️ Important

Each table must include:

* `student_id` **or**
* `id`

This ensures AI-generated SQL queries work correctly.

---

# 🚀 **3. Run Backend (FastAPI)**

Inside `/backend`:

```bash
cd backend
uvicorn main:app --reload
```

### Backend URL

```
http://127.0.0.1:8000
```

### Swagger Docs

```
http://127.0.0.1:8000/docs
```

---

# 🧪 **Backend Testing**

## **Login API**

POST

```
/login
```

Body:

```json
{
  "email": "teacher1@example.com",
  "password": "your_password"
}
```

## **Check User Info**

GET

```
/me
```

Header:

```
Authorization: Bearer <token>
```

## **Chat Query**

POST

```
/chat
```

Body:

```json
{
  "message": "show all students with pending fees"
}
```

---

# 🖥️ **4. Run Frontend (Flask)**

Inside `/frontend`:

```bash
cd frontend
python app.py
```

Frontend URL:

```
http://127.0.0.1:5000
```

---

# 🔗 **Frontend → Backend Configuration**

By default, frontend uses:

```
BACKEND_URL = "http://127.0.0.1:8000"
```

## **Running backend on another computer (LAN)?**

Example backend IP:

```
192.168.1.12
```

Update `frontend/.env`:

```
BACKEND_URL=http://192.168.1.12:8000
```

---

# 🌍 **Hostinger & Local Backend Notes**

* Backend does **not** run on Hostinger
* Only **MySQL** is remote

Backend connects like:

```
host = "srvXXXX.hstgr.io"
user = "uXXXX"
password = "****"
database = "uXXXX_db"
port = 3306
```

---

# 🔒 **JWT Authentication Flow**

* Login → Receive `
