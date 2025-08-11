##utils/apikey_utils.py
##
import sqlite3
import os

DB_PATH = "data/apikeys.db"
os.makedirs("data", exist_ok=True)

# Tablo oluşturma
with sqlite3.connect(DB_PATH) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apikeys (
            user_id INTEGER PRIMARY KEY,
            api_key TEXT,
            alarm_settings TEXT,
            trade_settings TEXT
        )
    """)

# API KEY EKLE/GÜNCELLE
def add_or_update_apikey(user_id: int, api_key: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, api_key) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET api_key=excluded.api_key
        """, (user_id, api_key))
        conn.commit()

# API KEY AL
def get_apikey(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT api_key FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

# ALARM AYARLARI EKLE/GÜNCELLE
def set_alarm_settings(user_id: int, settings: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, alarm_settings) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET alarm_settings=excluded.alarm_settings
        """, (user_id, settings))
        conn.commit()

# ALARM AYARLARINI GETİR
def get_alarm_settings(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT alarm_settings FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None

# TRADE AYARLARI EKLE/GÜNCELLE
def set_trade_settings(user_id: int, settings: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, trade_settings) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET trade_settings=excluded.trade_settings
        """, (user_id, settings))
        conn.commit()

# TRADE AYARLARINI GETİR
def get_trade_settings(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT trade_settings FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None
