"""
משיכת זמני שבת מ-Hebcal API
"""
import requests
import os
from datetime import datetime, timedelta
import pytz
import config

def get_shabbat_times_for(geoname_id: str, havdalah_offset: int):
    """
    מושך את זמני השבת הקרובה מ-Hebcal API
    
    Returns:
        dict: {'candle_lighting': datetime, 'havdalah': datetime}
        או None אם הייתה שגיאה
    """
    try:
        # בניית URL לפי הגדרות
        url = f"https://www.hebcal.com/shabbat?cfg=json&geonameid={geoname_id}"
        
        # הוספת הגדרת הבדלה אם הוגדרה
        if havdalah_offset > 0:
            url += f"&m={havdalah_offset}"
        else:
            url += "&M=on"  # חישוב אוטומטי (3 כוכבים)
        
        print(f"🔍 מושך זמני שבת מ-Hebcal: {url}")
        
        # שליחת בקשה ל-API
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # חיפוש זמני הדלקת נרות והבדלה
        candle_lighting = None
        havdalah = None
        
        for item in data.get('items', []):
            category = item.get('category', '')
            
            if category == 'candles':
                # זמן הדלקת נרות
                date_str = item.get('date')
                candle_lighting = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                
            elif category == 'havdalah':
                # זמן הבדלה
                date_str = item.get('date')
                havdalah = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        
        if candle_lighting and havdalah:
            print(f"✅ זמני שבת נמשכו בהצלחה!")
            print(f"🕯️ הדלקת נרות: {candle_lighting.strftime('%Y-%m-%d %H:%M')}")
            print(f"✨ הבדלה: {havdalah.strftime('%Y-%m-%d %H:%M')}")
            
            return {
                'candle_lighting': candle_lighting,
                'havdalah': havdalah,
                'title': data.get('title', 'שבת')
            }
        else:
            print("⚠️ לא נמצאו זמני שבת בתשובה מ-API")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ שגיאה בחיבור ל-Hebcal API: {e}")
        return None
    except Exception as e:
        print(f"❌ שגיאה כללית: {e}")
        return None


def get_next_shabbat_times_for(geoname_id: str, havdalah_offset: int):
    """
    מושך את זמני השבת הקרובה
    אם כבר עבר זמן הדלקת הנרות, מושך את השבת הבאה
    
    Returns:
        dict או None
    """
    times = get_shabbat_times_for(geoname_id, havdalah_offset)
    
    if not times:
        return None
    
    # בדיקה אם כבר עבר זמן הדלקת הנרות
    now = datetime.now(pytz.UTC)
    
    if times['candle_lighting'] < now:
        print("⚠️ זמן הדלקת נרות כבר עבר, ננסה למשוך את השבת הבאה...")
        # כאן אפשר להוסיף לוגיקה למשיכת שבת הבאה
        # לעת עתה נחזיר את מה שיש
    
    return times


# תאימות לאחור: שימוש בהגדרות הגלובליות מהקונפיג כאשר לא עובדים במצב רב-קבוצות
def get_shabbat_times():
    return get_shabbat_times_for(config.GEONAME_ID, config.HAVDALAH_OFFSET)


def get_next_shabbat_times():
    return get_next_shabbat_times_for(config.GEONAME_ID, config.HAVDALAH_OFFSET)


def search_geonames(query: str, max_results: int = 10):
    """
    חיפוש ערים בשירות GeoNames להחזרת geonameId לפי שם עיר.
    מחזיר רשימת תוצאות רלוונטיות (עשויות להיות ריקות אם אין הרשאות/שם משתמש).
    """
    username = getattr(config, 'GEONAMES_USERNAME', None) or os.getenv('GEONAMES_USERNAME')
    if not username:
        # ללא שם משתמש אי אפשר לבצע חיפוש דרך ה-API
        return []
    try:
        params = {
            'q': query,
            'maxRows': max_results,
            'lang': 'he',
            'isNameRequired': 'true',
            'featureClass': 'P',  # מקומות מיושבים
            'username': username,
        }
        url = 'http://api.geonames.org/searchJSON'
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('geonames', []):
            results.append({
                'name': item.get('name') or '',
                'countryName': item.get('countryName') or '',
                'adminName1': item.get('adminName1') or '',
                'geonameId': str(item.get('geonameId') or ''),
                'lat': item.get('lat'),
                'lng': item.get('lng'),
            })
        return results
    except Exception:
        return []


if __name__ == "__main__":
    # בדיקה של הפונקציה
    print("🧪 בודק משיכת זמני שבת...")
    times = get_next_shabbat_times()
    
    if times:
        print("\n✅ הבדיקה הצליחה!")
    else:
        print("\n❌ הבדיקה נכשלה")