import mysql.connector
import streamlit as st

# ---- Database Connection ----
def get_connection():
    try:
        connection = mysql.connector.connect(
            host="localhost",          # or your server IP
            user="root",               # your MySQL username
            password="your_password",  # your MySQL password
            database="fuzzydb"         # your database name
        )
        return connection
    except mysql.connector.Error as e:
        st.error(f"Database connection failed: {e}")
        return None
