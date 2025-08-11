##utils/apikey_utils.py
##
import sqlite3
from datetime import datetime, timedelta

DB_FILE = "data/user_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # API Keys tablosu
    c.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        user_id INTEGER PRIMARY KEY,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Alarm ayarları tablosu
    c.execute("""
    CREATE TABLE IF NOT EXISTS alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        symbol TEXT,
        price REAL,
        auto_delete INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Trade ayarları tablosu
    c.execute("""
    CREATE TABLE IF NOT EXISTS trade_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        settings_json TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# 🔹 API Key ekle/güncelle
def set_api_key(user_id, api_key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    INSERT INTO api_keys (user_id, api_key)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET api_key = excluded.api_key
    """, (user_id, api_key))
    conn.commit()
    conn.close()

def get_api_key(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT api_key FROM api_keys WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# 🔹 Alarm ekle
def add_alarm(user_id, symbol, price, auto_delete=True):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    INSERT INTO alarms (user_id, symbol, price, auto_delete)
    VALUES (?, ?, ?, ?)
    """, (user_id, symbol, price, 1 if auto_delete else 0))
    conn.commit()
    conn.close()

# 🔹 Alarm sil (manuel veya tetiklenince)
def delete_alarm(alarm_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM alarms WHERE id = ?", (alarm_id,))
    conn.commit()
    conn.close()

# 🔹 Alarm tetiklenince kontrol et ve gerekirse sil
def trigger_alarm(alarm_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT auto_delete FROM alarms WHERE id = ?", (alarm_id,))
    result = c.fetchone()
    if result and result[0] == 1:
        delete_alarm(alarm_id)
    conn.close()

# 🔹 Eski kayıtları sil (örn: 60 günden eski)
def cleanup_old_data(days=60):
    cutoff_date = datetime.now() - timedelta(days=days)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM alarms WHERE created_at < ?", (cutoff_date,))
    c.execute("DELETE FROM trade_settings WHERE created_at < ?", (cutoff_date,))
    conn.commit()
    conn.close()
