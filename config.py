"""
הגדרות הבוט - קריאת משתני סביבה
"""
import os
from dotenv import load_dotenv

# טעינת משתני סביבה מקובץ .env (רק בפיתוח מקומי)
load_dotenv()

# הגדרות חובה
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')  # ID של הקבוצה בטלגרם

# הגדרות מיקום לזמני שבת
LOCATION = os.getenv('LOCATION', 'Jerusalem')  # ברירת מחדל: ירושלים
GEONAME_ID = os.getenv('GEONAME_ID', '281184')  # Jerusalem GeoName ID

# הגדרות זמן
CANDLE_LIGHTING_OFFSET = int(os.getenv('CANDLE_LIGHTING_OFFSET', '18'))  # דקות לפני השקיעה
HAVDALAH_OFFSET = int(os.getenv('HAVDALAH_OFFSET', '0'))  # 0 = חישוב אוטומטי (3 כוכבים)

# הודעות מותאמות אישית (אופציונלי)
LOCK_MESSAGE = os.getenv('LOCK_MESSAGE', '🕯️ שבת שלום! הקבוצה ננעלת עד צאת השבת.')
UNLOCK_MESSAGE = os.getenv('UNLOCK_MESSAGE', '✨ שבוע טוב! הקבוצה נפתחה.')

# בדיקת הגדרות חובה
if not BOT_TOKEN:
    raise ValueError("❌ חסר TELEGRAM_BOT_TOKEN! הוסף אותו במשתני הסביבה")

if not CHAT_ID:
    raise ValueError("❌ חסר CHAT_ID! הוסף את ה-ID של הקבוצה במשתני הסביבה")

print("✅ הגדרות נטענו בהצלחה!")
print(f"📍 מיקום: {LOCATION}")
print(f"💬 קבוצה: {CHAT_ID}")