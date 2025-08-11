###alarm_handler.py → Alarm yönetimi işlevlerini yapar.

import logging
from datetime import datetime
from utils.apikey_utils import (
    add_alarm,
    get_user_alarms,
    delete_alarm_after_trigger,
    cleanup_old_alarms
)
from utils.monitoring import telegram_alert

LOG = logging.getLogger("alarm_handler")


def create_alarm(user_id: int, alarm_type: str, value: str):
    """Yeni alarm oluşturur"""
    add_alarm(user_id, alarm_type, value)
    LOG.info(f"Alarm eklendi | user_id={user_id}, type={alarm_type}, value={value}")
    telegram_alert(f"✅ Alarm oluşturuldu\n📌 Tür: {alarm_type}\n🎯 Değer: {value}")


def trigger_alarm(user_id: int, alarm_id: int, message: str):
    """
    Alarmı tetikler: Telegram'a mesaj atar ve otomatik olarak siler.
    """
    telegram_alert(f"🚨 Alarm Tetiklendi!\n\n{message}")
    delete_alarm_after_trigger(alarm_id)
    LOG.info(f"Alarm tetiklendi ve silindi | user_id={user_id}, alarm_id={alarm_id}")


def list_alarms(user_id: int):
    """Kullanıcının mevcut alarmlarını listeler"""
    alarms = get_user_alarms(user_id)
    if not alarms:
        telegram_alert("ℹ️ Henüz kayıtlı alarmınız yok.")
        return

    msg_lines = ["📋 Mevcut Alarmlar:"]
    for alarm in alarms:
        alarm_id, alarm_type, value, created_at = alarm
        msg_lines.append(f"#{alarm_id} | {alarm_type} = {value} | ⏱ {created_at}")
    telegram_alert("\n".join(msg_lines))


def cleanup_old(days: int = 60):
    """
    Belirtilen günden eski alarmları siler.
    Örn: cleanup_old(60) → 60 günden eski alarmlar silinir.
    """
    cleanup_old_alarms(days)
    LOG.info(f"{days} günden eski alarmlar temizlendi.")
    telegram_alert(f"🧹 {days} günden eski alarmlar temizlendi.")
