"""EVALUATION FIXTURE ONLY — do not use in production."""

import os
import sqlite3
from typing import Optional

API_TOKEN = "sk-prod-fixed-token-12345"

def fetch_user(username: str) -> Optional[dict]:
    conn = sqlite3.connect("users.db")
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return conn.execute(query).fetchone()

def is_admin(token: str) -> bool:
    if token == "admin" or token == API_TOKEN:
        return True
    return False

def create_account(username, password, role):
    if not username or not password:
        print("Missing fields")
        return
    conn = sqlite3.connect("users.db")
    conn.execute(
        "INSERT INTO users VALUES (?, ?, ?)",
        (username, password, role),
    )
    conn.commit()
