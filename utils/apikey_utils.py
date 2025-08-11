##utils/apikey_utils.py
##
## utils/apikey_utils.py
import sqlite3
import os
import time
from datetime import datetime, timedelta

DB_PATH = "data/apikeys.db"
os.makedirs("data", exist_ok=True)


# --- DB bağlantı fonksiyonu ---
def get_connection():
    return sqlite3.connect(DB_PATH)


# --- Tablo oluşturma ---
with get_connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS apikeys (
            user_id INTEGER PRIMARY KEY,
            api_key TEXT,
            alarm_settings TEXT,
            trade_settings TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            alarm_type TEXT,
            value TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


# --- API KEY İşlemleri ---
def add_or_update_apikey(user_id: int, api_key: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, api_key) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET api_key=excluded.api_key
        """, (user_id, api_key))
        conn.commit()

def get_apikey(user_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT api_key FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None


# --- Alarm Ayarları ---
def set_alarm_settings(user_id: int, settings: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, alarm_settings) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET alarm_settings=excluded.alarm_settings
        """, (user_id, settings))
        conn.commit()

def get_alarm_settings(user_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT alarm_settings FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None


# --- Trade Ayarları ---
def set_trade_settings(user_id: int, settings: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO apikeys (user_id, trade_settings) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET trade_settings=excluded.trade_settings
        """, (user_id, settings))
        conn.commit()

def get_trade_settings(user_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT trade_settings FROM apikeys WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None


# --- Alarm Yönetimi ---
def add_alarm(user_id: int, alarm_type: str, value: str):
    """Yeni alarm ekler"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO alarms (user_id, alarm_type, value) VALUES (?, ?, ?)
        """, (user_id, alarm_type, value))
        conn.commit()

def get_user_alarms(user_id: int):
    """Kullanıcının tüm alarmlarını getirir"""
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, alarm_type, value, created_at FROM alarms WHERE user_id = ?
        """, (user_id,)).fetchall()

def delete_alarm(alarm_id: int):
    """Belirli alarmı siler"""
    with get_connection() as conn:
        conn.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))
        conn.commit()

def delete_alarm_after_trigger(alarm_id: int):
    """Alarm çalıştıktan sonra otomatik siler"""
    delete_alarm(alarm_id)

def cleanup_old_alarms(days: int = 60):
    """Belirtilen günden eski alarmları temizler"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM alarms WHERE created_at < ?
        """, (cutoff_date.strftime("%Y-%m-%d %H:%M:%S"),))
        conn.commit()
