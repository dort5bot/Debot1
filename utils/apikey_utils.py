##utils/apikey_utils.py
import sqlite3
import os

DB_PATH = "data/apikeys.db"

os.makedirs("data", exist_ok=True)

# Tablo oluşturma
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apikeys (
            user_id INTEGER PRIMARY KEY,
            api_key TEXT
        )
    """)

def add_or_update_apikey(user_id: int, api_key: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, api_key) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET api_key=excluded.api_key
        """, (user_id, api_key))
        conn.commit()

def get_apikey(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT api_key FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

##
from data.apikey_data import load_apikeys, save_apikeys
import os

def set_user_apikey(user_id: int, apikey: str):
    apikeys = load_apikeys()
    apikeys[str(user_id)] = apikey
    save_apikeys(apikeys)
    return True

def get_user_apikey(user_id: int):
    apikeys = load_apikeys()
    return apikeys.get(str(user_id)) or os.getenv("DEFAULT_API_KEY")
    
