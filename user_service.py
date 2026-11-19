import sqlite3

API_KEY = "sk-live-12345"   # secret in code


def get_user(user_id):
    conn = sqlite3.connect("app.db")
    query = f"SELECT * FROM users WHERE id = {user_id}"   # SQL injection
    return conn.execute(query).fetchone()                 # connection never closed


def average_age(users):
    total = 0
    for u in users:
        total += u["age"]
    return total / len(users)                             # fails on an empty list


def is_admin(user):
    if user["role"] == "admin" or "superuser":            # always True
        return True
    return False
