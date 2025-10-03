# 🕯️ בוט "שומר שבת" לטלגרם

בוט אוטומטי שנועל את קבוצת הטלגרם שלך בכניסת שבת ופותח אותה בצאת השבת.

## ✨ תכונות

- 🔒 נעילה אוטומטית בזמן הדלקת נרות
- 🔓 פתיחה אוטומטית בזמן הבדלה
- 📍 תמיכה בכל מיקום בעולם (דרך GeoNames)
- 🔄 רענון שבועי אוטומטי של זמני שבת
- 💬 הודעות מותאמות אישית
- ☁️ פריסה חינמית על Render

## 🚀 התקנה מהירה

### 1️⃣ יצירת הבוט בטלגרם

1. פתח שיחה עם [@BotFather](https://t.me/BotFather)
2. שלח /newbot וענה על השאלות
3. שמור את הטוקן שקיבלת (נראה כך: 1234567890:ABCdef...)

### 2️⃣ הוספת הבוט לקבוצה

1. צור קבוצה חדשה או בחר קיימת
2. הוסף את הבוט לקבוצה
3. חשוב: הפוך את הבוט ל-Admin עם הרשאות:
   - ✅ Change Group Info
   - ✅ Delete Messages
   - ✅ Restrict Members

### 3️⃣ מציאת ה-ID של הקבוצה

1. הוסף את [@getidsbot](https://t.me/getidsbot) לקבוצה
2. הבוט יתן לך את ה-ID של הקבוצה (מתחיל עם -100...)
3. שמור את המספר הזה

### 4️⃣ העלאה ל-Render

#### א. הכנת הקוד

# שכפל את הפרויקט
git clone <your-repo-url>
cd shabbat-bot

# צור קובץ .env מקומי (לבדיקות)
cp .env.example .env
# ערוך את .env עם הערכים האמיתיים
#### ב. יצירת Service ב-Render

1. היכנס ל-[Render Dashboard](https://dashboard.render.com/)
2. לחץ New + → Background Worker
3. חבר את ה-repository שלך מ-GitHub
4. הגדרות:
   - Name: shabbat-bot (או כל שם שתרצה)
   - Environment: Python 3
   - Build Command: pip install -r requirements.txt
   - Start Command: משאיר ריק (Render ישתמש ב-Procfile)

#### ג. הוספת משתני סביבה ב-Render

לחץ על Environment והוסף:

| Key | Value | דוגמה |
|-----|-------|--------|
| TELEGRAM_BOT_TOKEN | הטוקן מ-BotFather | 1234567890:ABC... |
| CHAT_ID | ID של הקבוצה | -1001234567890 |
| GEONAME_ID | מזהה המיקום | 281184 (ירושלים) |
| LOCATION | שם המיקום | Jerusalem |

אופציונלי:
- CANDLE_LIGHTING_OFFSET - דקות לפני שקיעה (ברירת מחדל: 18)
- HAVDALAH_OFFSET - דקות אחרי שקיעה (ברירת מחדל: 0 = אוטומטי)
- LOCK_MESSAGE - הודעה בכניסת שבת
- UNLOCK_MESSAGE - הודעה בצאת שבת

#### ד. פריסה

1. לחץ Create Background Worker
2. Render יתחיל לבנות ולהריץ את הבוט
3. בדוק ב-Logs שהבוט פועל תקין

## 🔍 מציאת GeoName ID למיקום שלך

1. היכנס ל-[GeoNames.org](https://www.geonames.org/)
2. חפש את העיר שלך
3. לחץ על התוצאה
4. ה-ID מופיע ב-URL: geonames.org/XXXXXXX

### ערים נפוצות בישראל:

| עיר | GeoName ID |
|-----|-----------|
| ירושלים | 281184 |
| תל אביב | 293397 |
| חיפה | 294801 |
| באר שבע | 295530 |
| נתניה | 293842 |
| אשדוד | 295629 |
| ראשון לציון | 293788 |

## 📁 מבנה הפרויקט

shabbat-bot/
├── bot.py                 # קוד ראשי
├── config.py             # הגדרות
├── shabbat_times.py      # משיכת זמני שבת
├── requirements.txt      # תלויות
├── Procfile             # הגדרות Render
├── .env.example         # תבנית משתני סביבה
├── .gitignore           # קבצים להתעלם
└── README.md            # התיעוד הזה
## 🧪 בדיקה מקומית

# התקנת תלויות
pip install -r requirements.txt

# הרצת הבוט
python bot.py

# בדיקת משיכת זמני שבת
python shabbat_times.py
## 🔧 פתרון בעיות

### הבוט לא נועל את הקבוצה?

- ✅ בדוק שהבוט הוא Admin בקבוצה
- ✅ בדוק שהבוט קיבל הרשאות Restrict Members
- ✅ בדוק ב-Logs של Render שאין שגיאות

### זמני השבת לא נכונים?

- ✅ ודא שה-GEONAME_ID נכון למיקום שלך
- ✅ בדוק את ההגדרות ב-[Hebcal.com](https://www.hebcal.com/shabbat)

### הבוט לא עובד אחרי deployment?

- ✅ ודא שכל משתני הסביבה הוזנו ב-Render
- ✅ בדוק ב-Logs של Render מה השגיאה
- ✅ ודא שהבוט פועל כ-Background Worker (לא Web Service)

## 📝 לוגים

כדי לראות את הלוגים של הבוט:

1. היכנס ל-Render Dashboard
2. בחר את ה-service שלך
3. לחץ Logs

תראה הודעות כמו:
✅ הגדרות נטענו בהצלחה!
✅ מחובר כ: @your_bot_username
⏰ תוזמן נעילה: 2025-10-03 18:23
⏰ תוזמן פתיחה: 2025-10-04 19:45
## 🎨 התאמה אישית

### שינוי הודעות

ערוך את משתני הסביבה:
LOCK_MESSAGE=🌙 ערב שבת טוב! נתראה במוצ"ש
UNLOCK_MESSAGE=🌟 מוצאי שבת טוב!
### שינוי זמני הדלקה

CANDLE_LIGHTING_OFFSET=30  # 30 דקות לפני שקיעה
HAVDALAH_OFFSET=50         # 50 דקות אחרי שקיעה
## 🛡️ אבטחה
- ❌ לעולם אל תעלה את קובץ .env ל-Git
- ✅ השתמש רק במשתני סביבה של Render
- ✅ הבוט לא שומר מידע רגיש
- ✅ כל התקשורת מוצפנת (HTTPS/TLS)

## 📚 טכנולוגיות

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v22.5
- [APScheduler](https://github.com/agronholm/apscheduler) v3.11.0
- [Hebcal API](https://www.hebcal.com/home/developer-apis) - זמני שבת
- [Render](https://render.com/) - hosting חינמי

## 🤝 תרומה

מצאת באג? יש רעיון לשיפור? פתח Issue או Pull Request!

## 📄 רישיון

פרויקט זה הוא קוד פתוח ללא רישיון מגביל. תרגיש חופשי להשתמש, לשנות ולשתף!

## 💝 תודות

- תודה ל-[@BotFather](https://t.me/BotFather) על יצירת הבוטים
- תודה ל-[Hebcal](https://www.hebcal.com/) על ה-API המדהים
- תודה ל-[Render](https://render.com/) על ה-hosting החינמי

---

שבת שלום! 🕯️✨