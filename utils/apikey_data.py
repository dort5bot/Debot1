##apikey_data.py

import sqlite3
import os

DB_PATH = os.path.join("data", "bot_database.sqlite")

def init_api_table():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id INTEGER PRIMARY KEY,
                api_key TEXT NOT NULL,
                secret_key TEXT NOT NULL
            )
        """)
    print("✅ API key tablosu hazır")

def save_api_key(user_id: int, api_key: str, secret_key: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO user_api_keys (user_id, api_key, secret_key)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                api_key = excluded.api_key,
                secret_key = excluded.secret_key
        """, (user_id, api_key, secret_key))
    return True

def get_api_key(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT api_key, secret_key FROM user_api_keys
            WHERE user_id = ?
        """, (user_id,)).fetchone()
    return row if row else (None, None)
