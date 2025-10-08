"""
הגדרות הבוט - קריאת משתני סביבה
"""
import os
import json
from dotenv import load_dotenv

# טעינת משתני סביבה מקובץ .env (רק בפיתוח מקומי)
load_dotenv()

# הגדרות חובה
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')  # ID של הקבוצה בטלגרם (לשימוש במצב יחיד)

# הגדרות מיקום לזמני שבת
LOCATION = os.getenv('LOCATION', 'Jerusalem')  # ברירת מחדל: ירושלים
GEONAME_ID = os.getenv('GEONAME_ID', '281184')  # Jerusalem GeoName ID

# הגדרות זמן
CANDLE_LIGHTING_OFFSET = int(os.getenv('CANDLE_LIGHTING_OFFSET', '18'))  # דקות לפני השקיעה
HAVDALAH_OFFSET = int(os.getenv('HAVDALAH_OFFSET', '0'))  # 0 = חישוב אוטומטי (3 כוכבים)

# הודעות מותאמות אישית (אופציונלי)
LOCK_MESSAGE = os.getenv('LOCK_MESSAGE', '🕯️ שבת שלום! הקבוצה ננעלת עד צאת השבת.')
UNLOCK_MESSAGE = os.getenv('UNLOCK_MESSAGE', '✨ שבוע טוב! הקבוצה נפתחה.')

# תמיכה בריבוי קבוצות/מיקומים דרך JSON במשתנה סביבה GROUPS_CONFIG
# פורמט צפוי (דוגמה):
# [
#   {
#     "chat_id": "-1001234567890",
#     "location": "Jerusalem",
#     "geoname_id": "281184",
#     "candle_lighting_offset": 18,
#     "havdalah_offset": 0,
#     "lock_message": "🕯️ שבת שלום!",
#     "unlock_message": "✨ שבוע טוב!"
#   }
# ]
GROUPS: list[dict] = []
GROUPS_CONFIG = os.getenv('GROUPS_CONFIG')

if GROUPS_CONFIG:
    try:
        raw = json.loads(GROUPS_CONFIG)
        if isinstance(raw, dict):
            raw = [raw]
        if not isinstance(raw, list):
            raise ValueError("GROUPS_CONFIG must be a JSON array or object")
        for idx, item in enumerate(raw):
            chat_id = str(item.get('chat_id') or item.get('CHAT_ID') or '').strip()
            geoname_id = str(item.get('geoname_id') or item.get('GEONAME_ID') or '').strip()
            if not chat_id or not geoname_id:
                raise ValueError(f"group index {idx}: chat_id and geoname_id are required")

            group_location = item.get('location') or item.get('LOCATION') or LOCATION
            group_candle_offset = int(str(item.get('candle_lighting_offset') or item.get('CANDLE_LIGHTING_OFFSET') or CANDLE_LIGHTING_OFFSET))
            group_havdalah_offset = int(str(item.get('havdalah_offset') or item.get('HAVDALAH_OFFSET') or HAVDALAH_OFFSET))
            group_lock_msg = item.get('lock_message') or item.get('LOCK_MESSAGE') or LOCK_MESSAGE
            group_unlock_msg = item.get('unlock_message') or item.get('UNLOCK_MESSAGE') or UNLOCK_MESSAGE

            GROUPS.append({
                'chat_id': chat_id,
                'location': group_location,
                'geoname_id': geoname_id,
                'candle_lighting_offset': group_candle_offset,
                'havdalah_offset': group_havdalah_offset,
                'lock_message': group_lock_msg,
                'unlock_message': group_unlock_msg,
            })
    except Exception as e:
        raise ValueError(f"❌ GROUPS_CONFIG שגוי: {e}")

# בדיקת הגדרות חובה
if not BOT_TOKEN:
    raise ValueError("❌ חסר TELEGRAM_BOT_TOKEN! הוסף אותו במשתני הסביבה")

# אם לא הוגדר GROUPS_CONFIG - נשתמש בהגדרות יחידניות אם קיימות, אחרת נאפשר ריצה ללא קבוצות מוגדרות
if not GROUPS:
    if CHAT_ID:
        GROUPS = [{
            'chat_id': CHAT_ID,
            'location': LOCATION,
            'geoname_id': GEONAME_ID,
            'candle_lighting_offset': CANDLE_LIGHTING_OFFSET,
            'havdalah_offset': HAVDALAH_OFFSET,
            'lock_message': LOCK_MESSAGE,
            'unlock_message': UNLOCK_MESSAGE,
        }]
    else:
        GROUPS = []

print("✅ הגדרות נטענו בהצלחה!")
if GROUPS:
    for g in GROUPS:
        print(f"💬 קבוצה: {g['chat_id']} | 📍 מיקום: {g['location']} | 🆔 GeoName: {g['geoname_id']}")
else:
    print("ℹ️ אין קבוצות מוגדרות מראש. ניתן להגדיר קבוצה חדשה מתוך טלגרם באמצעות פקודות אדמין.")