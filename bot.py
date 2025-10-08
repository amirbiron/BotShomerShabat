"""
בוט "שומר שבת" לטלגרם
נועל את הקבוצה בכניסת שבת ופותח בצאת השבת
"""
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, Bot, ChatPermissions, ReplyKeyboardMarkup, KeyboardButton, BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

from activity_reporter import create_reporter

import config
from shabbat_times import get_next_shabbat_times, get_next_shabbat_times_for, search_geonames

# הגדרת logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# אתחול הסקדיולר
scheduler = AsyncIOScheduler()

# משתנה גלובלי לשמירת האפליקציה
application = None
STORAGE_FILE = 'groups.json'
_storage_cache: dict[str, dict] = {}
_search_cache_by_chat: dict[str, dict[str, str]] = {}

# ה (שמור בראש הקובץ אחרי טעינת משתנים)
reporter = create_reporter(
    mongodb_uri="mongodb+srv://mumin:M43M2TFgLfGvhBwY@muminai.tm6x81b.mongodb.net/?retryWrites=true&w=majority&appName=muminAI",
    service_id="srv-d3fvmnodl3ps7392r69g",
    service_name="ShomerShabat"
)

def _load_storage():
    import json, os
    global _storage_cache
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _storage_cache = data
                else:
                    _storage_cache = {}
        except Exception as e:
            logger.error(f"❌ קריאת קובץ אחסון נכשלה: {e}")
            _storage_cache = {}
    else:
        _storage_cache = {}


def _save_storage():
    import json
    try:
        with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(_storage_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"❌ שמירת קובץ אחסון נכשלה: {e}")



async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    מטפל בשגיאות גלובליות כדי למנוע ספאמים בלוגים ללא error handlers
    """
    logger.exception("Unhandled exception while processing an update", exc_info=context.error)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    בודק אם המשתמש הוא אדמין בקבוצה
    """
    try:
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except:
        return False


def is_valid_geoname_id(value: str) -> bool:
    """
    מזהה GeoName תקין חייב להיות מספרי (כפי שנדרש על ידי Hebcal geonameid)
    """
    try:
        return str(value).strip().isdigit()
    except Exception:
        return False


def build_command_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    """
    בונה מקשי מקלדת עם כל הפקודות. מציג פקודות אדמין רק לאדמינים.
    """
    user_rows = [
        [KeyboardButton("/times"), KeyboardButton("/status")],
        [KeyboardButton("/help"), KeyboardButton("/menu")],
    ]

    admin_rows = []
    if is_admin:
        admin_rows = [
            [KeyboardButton("/lock"), KeyboardButton("/unlock")],
            [KeyboardButton("/settings"), KeyboardButton("/admin_help")],
            [KeyboardButton("/setgeo"), KeyboardButton("/findgeo")],
            [KeyboardButton("/setoffsets")],
            [KeyboardButton("/setmessages")],
        ]

    return ReplyKeyboardMarkup(
        keyboard=user_rows + admin_rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
        selective=True,
        input_field_placeholder="בחר פקודה…",
    )

def _to_int_chat_id(chat_id: str | int) -> int:
    try:
        return int(chat_id)
    except Exception:
        # בטלגרם chat_id יכול להיות מחרוזת; ננסה להסיר רווחים וסימנים לא נחוצים
        return int(str(chat_id).strip())


def _get_group_config(chat_id: int | str) -> dict | None:
    # חיפוש בהגדרות הסביבה
    for g in config.GROUPS:
        if str(g['chat_id']) == str(chat_id):
            return g
    # חיפוש באחסון הדינמי
    key = str(chat_id)
    g = _storage_cache.get(key)
    if g:
        return g
    return None


async def lock_group_for(chat_id: int | str, lock_message: str, context: ContextTypes.DEFAULT_TYPE = None):
    """
    נועל את הקבוצה - מאפשר רק לאדמינים לשלוח הודעות
    """
    try:
        logger.info(f"🔒 נועל את הקבוצה {chat_id}")
        
        bot = application.bot if application else context.bot
        
        # הרשאות מוגבלות - רק אדמינים יכולים לשלוח
        # התאמה ל-PTB/Bot API חדשים: פירוק הרשאת מדיה לסוגים
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )
        
        # החלת ההרשאות על הקבוצה
        await bot.set_chat_permissions(
            chat_id=_to_int_chat_id(chat_id),
            permissions=permissions
        )
        
        # שליחת הודעה לקבוצה
        await bot.send_message(chat_id=_to_int_chat_id(chat_id), text=lock_message)
        
        logger.info("✅ הקבוצה ננעלה בהצלחה!")
        
    except TelegramError as e:
        logger.error(f"❌ שגיאה בנעילת הקבוצה: {e}")


async def unlock_group_for(chat_id: int | str, unlock_message: str, context: ContextTypes.DEFAULT_TYPE = None):
    """
    פותח את הקבוצה - מאפשר לכולם לשלוח הודעות
    """
    try:
        logger.info(f"🔓 פותח את הקבוצה {chat_id}")
        
        bot = application.bot if application else context.bot
        
        # הרשאות מלאות - כולם יכולים לשלוח
        # התאמה ל-PTB/Bot API חדשים: פירוק הרשאת מדיה לסוגים
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
        
        # החלת ההרשאות על הקבוצה
        await bot.set_chat_permissions(
            chat_id=_to_int_chat_id(chat_id),
            permissions=permissions
        )
        
        # שליחת הודעה לקבוצה
        await bot.send_message(chat_id=_to_int_chat_id(chat_id), text=unlock_message)
        
        logger.info("✅ הקבוצה נפתחה בהצלחה!")
        
    except TelegramError as e:
        logger.error(f"❌ שגיאה בפתיחת הקבוצה: {e}")


# תאימות לאחור: הפונקציות המקוריות פועלות על הקבוצה הראשונה בקונפיג
async def lock_group(context: ContextTypes.DEFAULT_TYPE = None):
    g = config.GROUPS[0]
    await lock_group_for(g['chat_id'], g['lock_message'], context)


async def unlock_group(context: ContextTypes.DEFAULT_TYPE = None):
    g = config.GROUPS[0]
    await unlock_group_for(g['chat_id'], g['unlock_message'], context)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /start - הודעת ברוכים הבאים
    """
    reporter.report_activity(update.effective_user.id)
    welcome_msg = """
🕯️ ברוך הבא לבוט "שומר שבת"!

שלום 👋
אני בוט אוטומטי שנועל את הקבוצה בכניסת שבת ופותח אותה בצאת השבת – בדיוק בזמן, לפי המיקום שהוגדר.

---

📋 פקודות כלליות
/times – הצגת זמני השבת הקרובה
/status – מצב הבוט והתזמונים הנוכחיים
/help – עזרה ומידע למשתמשים

---

🔐 פקודות אדמין
(זמינות רק למנהלי הקבוצה)
/lock – נעילה ידנית של הקבוצה
/unlock – פתיחה ידנית של הקבוצה
/settings – הצגת ההגדרות הקיימות
/setgeo <GEONAME\_ID> [שם-מיקום] – הגדרת מיקום הקבוצה (חובה למיקום מדויק)
/setoffsets <CANDLE\_MIN> [HAVDALAH\_MIN] – הגדרת דקות לפני הדלקת נרות ואחרי הבדלה
/setmessages <LOCK> || <UNLOCK> – הודעות נעילה ופתיחה מותאמות אישית
/admin\_help – עזרה והסברים מפורטים לפקודות אדמין

---

✨ הבוט פועל אוטומטית!
אין צורך להפעיל ידנית – רק להגדיר מיקום פעם אחת, והכול יתבצע מעצמו בכל שבוע 🙌
    """
    is_admin_user = await is_admin(update, context)
    await update.message.reply_text(
        welcome_msg,
        parse_mode='Markdown',
        reply_markup=build_command_keyboard(is_admin_user)
    )


async def cmd_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /times - הצגת זמני שבת
    """
    reporter.report_activity(update.effective_user.id)
    await update.message.reply_text("🔍 מושך זמני שבת...")
    
    # זיהוי הקבוצה הנוכחית לפי ההודעה
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or (config.GROUPS[0] if config.GROUPS else None)
    if not g:
        await update.message.reply_text("⚠️ הקבוצה לא מוגדרת. אדמין: הגדרו מיקום עם /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    if not is_valid_geoname_id(g.get('geoname_id', '')):
        await update.message.reply_text("⚠️ מיקום לא תקין: GeoName ID חייב להיות מספרי. הגדרה מחדש: /setgeo <GEONAME_ID> [שם-מיקום]\nדוגמה: /setgeo 281184 ירושלים")
        return
    times = get_next_shabbat_times_for(g['geoname_id'], g['havdalah_offset'])
    
    if not times:
        await update.message.reply_text("❌ לא הצלחתי למשוך זמני שבת. נסה שוב מאוחר יותר.")
        return
    
    candle = times['candle_lighting'].strftime('%d/%m/%Y %H:%M')
    havdalah = times['havdalah'].strftime('%d/%m/%Y %H:%M')
    title = times.get('title', 'שבת')
    
    msg = f"""
🕯️ **זמני {title}**

🔥 **הדלקת נרות:** {candle}
✨ **הבדלה:** {havdalah}

📍 מיקום: {g['location']}
    """
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /status - סטטוס הבוט
    """
    reporter.report_activity(update.effective_user.id)
    # בדיקת תזמונים קיימים
    chat_id = update.effective_chat.id
    gid = str(chat_id)
    lock_job = scheduler.get_job(f'lock_shabbat_{gid}')
    unlock_job = scheduler.get_job(f'unlock_shabbat_{gid}')
    refresh_job = scheduler.get_job(f'weekly_refresh_{gid}')
    
    msg = "🤖 **סטטוס הבוט**\n\n"
    
    if lock_job:
        next_lock = lock_job.next_run_time.strftime('%d/%m/%Y %H:%M')
        msg += f"🔒 נעילה הבאה: {next_lock}\n"
    else:
        msg += "🔒 נעילה: לא מתוזמן\n"
    
    if unlock_job:
        next_unlock = unlock_job.next_run_time.strftime('%d/%m/%Y %H:%M')
        msg += f"🔓 פתיחה הבאה: {next_unlock}\n"
    else:
        msg += "🔓 פתיחה: לא מתוזמן\n"
    
    if refresh_job:
        next_refresh = refresh_job.next_run_time.strftime('%d/%m/%Y %H:%M')
        msg += f"🔄 רענון הבא: {next_refresh}\n"
    
    g = _get_group_config(chat_id) or (config.GROUPS[0] if config.GROUPS else None)
    if not g:
        msg += "\n📍 מיקום: לא מוגדר\nהגדרה: /setgeo <GEONAME_ID> [שם-מיקום]"
        await update.message.reply_text(msg, parse_mode='Markdown')
        return
    msg += f"\n📍 מיקום: {g['location']}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /settings - הצגת הגדרות (אדמין בלבד)
    """
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or (config.GROUPS[0] if config.GROUPS else None)
    if not g:
        await update.message.reply_text("⚙️ אין הגדרות לקבוצה זו. הגדרה ראשונית: /setgeo <GEONAME_ID> [שם-מיקום]", parse_mode='Markdown')
        return
    msg = f"""
⚙️ **הגדרות הבוט**

📍 **מיקום:** {g['location']}
🆔 **GeoName ID:** {g['geoname_id']}

⏰ **זמנים:**
• הדלקת נרות: {g['candle_lighting_offset']} דקות לפני שקיעה
• הבדלה: {g['havdalah_offset'] if g['havdalah_offset'] > 0 else 'אוטומטי (3 כוכבים)'}

💬 **הודעות:**
• נעילה: {g['lock_message']}
• פתיחה: {g['unlock_message']}
    """
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_setgeo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("שימוש: /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    geoname_id = args[0].strip()
    if not is_valid_geoname_id(geoname_id):
        await update.message.reply_text("❌ GeoName ID חייב להיות מספרי. לדוגמה: 281184 (ירושלים).\nנסה: /setgeo 281184 ירושלים")
        return
    location = ' '.join(args[1:]) if len(args) > 1 else 'Custom'
    chat_id = update.effective_chat.id
    key = str(chat_id)
    # ברירות מחדל
    g = _get_group_config(chat_id) or {
        'chat_id': key,
        'candle_lighting_offset': config.CANDLE_LIGHTING_OFFSET,
        'havdalah_offset': config.HAVDALAH_OFFSET,
        'lock_message': config.LOCK_MESSAGE,
        'unlock_message': config.UNLOCK_MESSAGE,
    }
    g.update({'geoname_id': geoname_id, 'location': location})
    _storage_cache[key] = g
    _save_storage()
    await update.message.reply_text(f"✅ הוגדר מיקום לקבוצה זו: {location} (GeoName: {geoname_id})")
    # עדכון תזמון
    schedule_shabbat()


async def cmd_setoffsets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("שימוש: /setoffsets <CANDLE_MINUTES> [HAVDALAH_MINUTES]")
        return
    try:
        candle = int(args[0])
        havdalah = int(args[1]) if len(args) > 1 else (config.HAVDALAH_OFFSET)
    except ValueError:
        await update.message.reply_text("ערכים לא חוקיים. יש להזין מספרים שלמים.")
        return
    chat_id = update.effective_chat.id
    key = str(chat_id)
    g = _get_group_config(chat_id)
    if not g:
        await update.message.reply_text("⚠️ יש להגדיר קודם מיקום: /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    g['candle_lighting_offset'] = candle
    g['havdalah_offset'] = havdalah
    _storage_cache[key] = g
    _save_storage()
    await update.message.reply_text(f"✅ עודכנו זמני הדלקה/הבדלה: {candle}/{havdalah} דקות")
    schedule_shabbat()


async def cmd_setmessages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    # פורמט: /setmessages <LOCK_MESSAGE> || <UNLOCK_MESSAGE>
    text = update.message.text or ''
    parts = text.split(' ', 1)
    if len(parts) < 2 or '||' not in parts[1]:
        await update.message.reply_text("שימוש: /setmessages <LOCK_MESSAGE> || <UNLOCK_MESSAGE>")
        return
    lock_msg_raw, unlock_msg_raw = parts[1].split('||', 1)
    lock_msg = lock_msg_raw.strip()
    unlock_msg = unlock_msg_raw.strip()
    chat_id = update.effective_chat.id
    key = str(chat_id)
    g = _get_group_config(chat_id)
    if not g:
        await update.message.reply_text("⚠️ יש להגדיר קודם מיקום: /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    g['lock_message'] = lock_msg or g.get('lock_message') or config.LOCK_MESSAGE
    g['unlock_message'] = unlock_msg or g.get('unlock_message') or config.UNLOCK_MESSAGE
    _storage_cache[key] = g
    _save_storage()
    await update.message.reply_text("✅ עודכנו הודעות הנעילה והפתיחה לקבוצה זו")


async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /lock - נעילה ידנית (אדמין בלבד)
    """
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or (config.GROUPS[0] if config.GROUPS else None)
    if not g:
        await update.message.reply_text("⚠️ הקבוצה לא מוגדרת. הגדירו תחילה מיקום עם /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    await update.message.reply_text("🔒 נועל את הקבוצה...")
    await lock_group_for(g['chat_id'], g['lock_message'], context)
    await update.message.reply_text("✅ הקבוצה ננעלה!")


async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /unlock - פתיחה ידנית (אדמין בלבד)
    """
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or (config.GROUPS[0] if config.GROUPS else None)
    if not g:
        await update.message.reply_text("⚠️ הקבוצה לא מוגדרת. הגדירו תחילה מיקום עם /setgeo <GEONAME_ID> [שם-מיקום]")
        return
    await update.message.reply_text("🔓 פותח את הקבוצה...")
    await unlock_group_for(g['chat_id'], g['unlock_message'], context)
    await update.message.reply_text("✅ הקבוצה נפתחה!")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /help - עזרה
    """
    reporter.report_activity(update.effective_user.id)
    help_msg = """
🕯️ עזרה - בוט שומר שבת

מה הבוט עושה?
הבוט נועל את הקבוצה אוטומטית בזמן הדלקת נרות ופותח אותה בזמן הבדלה.

📋 פקודות כלליות:
• /times - הצגת זמני השבת הקרובה
• /status - סטטוס הבוט והתזמונים הקרובים
• /help - הודעת עזרה זו

🔐 פקודות אדמין:
• /lock - נעילה ידנית של הקבוצה
• /unlock - פתיחה ידנית של הקבוצה
• /settings - הצגת הגדרות הבוט

❓ שאלות נפוצות:

איך הבוט יודע את זמני השבת?
הבוט משתמש ב-Hebcal API ומושך את הזמנים לפי המיקום שהוגדר.

מה אם זמני השבת לא מדויקים?
ניתן לשנות את ההגדרות (מיקום, דקות לפני/אחרי) במשתני הסביבה.

האם הבוט פועל גם בחגים?
כרגע הבוט פועל רק בשבת. תמיכה בחגים תתווסף בעתיד.

✨ נתקלת בבעיה? פנה למפתח הבוט: @moominAmir
    """
    is_admin_user = await is_admin(update, context)
    await update.message.reply_text(
        help_msg,
        parse_mode='Markdown',
        reply_markup=build_command_keyboard(is_admin_user)
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /menu - הצגת מקשי הפקודות
    """
    reporter.report_activity(update.effective_user.id)
    is_admin_user = await is_admin(update, context)
    await update.message.reply_text(
        "📲 תפריט הפקודות",
        reply_markup=build_command_keyboard(is_admin_user)
    )


async def cmd_admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter.report_activity(update.effective_user.id)
    msg = """
פקודות בוט שומר שבת

שלום 👋
הבוט נועד לעזור לקבוצות לשמור שבת בצורה נוחה – עם זמני נעילה ופתיחה אוטומטיים, הודעות מותאמות ועוד.
להלן הפקודות הזמינות לאדמינים:

---

🗺️ /setgeo <GEONAME\_ID> [שם-מיקום]
הגדרת מיקום הקבוצה לפי GeoNames (חובה).
אפשר לציין גם שם תצוגה (אופציונלי).
לאחר ההגדרה, הבוט יעדכן את זמני השבת לפי המיקום החדש.
נשמר בקובץ ההגדרות של הקבוצה.

ℹ️ שים לב: GeoName ID הוא מספרי בלבד (למשל: 281184 לירושלים)

🔎 /findgeo <שם-עיר>
חיפוש מזהה GeoName לפי שם עיר והצגת כפתורי בחירה מהירים.

---

🕯️ /setoffsets <CANDLE\_MIN> [HAVDALAH\_MIN]
הגדרת זמני הדלקת נרות והבדלה.

<CANDLE\_MIN> – כמה דקות לפני שקיעה מדליקים נרות.

[HAVDALAH\_MIN] – כמה דקות אחרי שקיעה עושים הבדלה (אם לא מצוין, נשמר הערך הקודם).
ברירת מחדל: 0 = שלושה כוכבים.
הבוט יעדכן את התזמון של ההודעות בהתאם.

---

🔒 /setmessages <LOCK> || <UNLOCK>
הגדרת הודעות נעילה ופתיחה מותאמות אישית.
ההודעות נפרדות בעזרת ||.
דוגמה:
/setmessages שבת שלום 🌙 || שבוע טוב 🌅
    """
    await update.message.reply_text(msg, parse_mode='Markdown')


def schedule_shabbat():
    """
    מתזמן את נעילת ופתיחת הקבוצות לפי זמני השבת עבור כל קבוצה
    """
    logger.info("📅 מתזמן את זמני השבת הקרובה לכל הקבוצות...")

    # איחוד קבוצות מהקונפיג ומהאחסון הדינמי
    merged_by_id: dict[str, dict] = {}
    for g in config.GROUPS:
        merged_by_id[str(g['chat_id'])] = dict(g)
    for key, sg in _storage_cache.items():
        # העדפה להגדרות מהאחסון (דינמי)
        merged_by_id[str(key)] = dict(sg)

    for g in merged_by_id.values():
        gid = str(g['chat_id'])

        # משיכת זמני שבת עבור הקבוצה
        if not is_valid_geoname_id(g.get('geoname_id', '')):
            logger.error(f"❌ group {gid}: geoname_id לא תקין (צריך להיות מספרי). מדלג על תזמון.")
            continue
        times = get_next_shabbat_times_for(g['geoname_id'], g['havdalah_offset'])
        if not times:
            logger.error(f"❌ לא הצלחתי למשוך זמני שבת לקבוצה {gid}. ננסה לרענן בעוד שעה.")
            retry_time = datetime.now().replace(microsecond=0) + timedelta(hours=1)
            scheduler.add_job(schedule_shabbat, DateTrigger(run_date=retry_time), id=f'retry_schedule_{gid}', replace_existing=True)
            continue

        candle_lighting = times['candle_lighting']
        havdalah = times['havdalah']

        # הסרת תזמונים קיימים לקבוצה זו (אם יש)
        for job_id in [f'lock_shabbat_{gid}', f'unlock_shabbat_{gid}']:
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

        # תזמון נעילה בכניסת שבת
        scheduler.add_job(
            lock_group_for,
            DateTrigger(run_date=candle_lighting),
            id=f'lock_shabbat_{gid}',
            args=[g['chat_id'], g['lock_message']],
            replace_existing=True,
        )
        logger.info(f"⏰ תוזמן נעילה לקבוצה {gid}: {candle_lighting.strftime('%Y-%m-%d %H:%M')}")

        # תזמון פתיחה בצאת השבת
        scheduler.add_job(
            unlock_group_for,
            DateTrigger(run_date=havdalah),
            id=f'unlock_shabbat_{gid}',
            args=[g['chat_id'], g['unlock_message']],
            replace_existing=True,
        )
        logger.info(f"⏰ תוזמן פתיחה לקבוצה {gid}: {havdalah.strftime('%Y-%m-%d %H:%M')}")

        # תזמון רענון שבועי פרטני לכל קבוצה (ביום ראשון בלילה יחסית ל-UTC)
        next_refresh = havdalah.replace(hour=23, minute=0, second=0, microsecond=0)
        scheduler.add_job(
            schedule_shabbat,
            DateTrigger(run_date=next_refresh),
            id=f'weekly_refresh_{gid}',
            replace_existing=True,
        )
        logger.info(f"🔄 רענון שבועי עבור {gid} יתבצע ב: {next_refresh.strftime('%Y-%m-%d %H:%M')}")


async def cmd_findgeo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /findgeo - חיפוש GeoName ID לפי שם עיר (אדמין בלבד)
    """
    reporter.report_activity(update.effective_user.id)
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    args = context.args
    if not args:
        await update.message.reply_text("שימוש: /findgeo <שם-עיר>\nלדוגמה: /findgeo Jerusalem או /findgeo תל אביב")
        return
    query = ' '.join(args).strip()
    results = search_geonames(query, max_results=8)
    if not results:
        # לינק לחיפוש ידני
        from urllib.parse import quote
        url = f"https://www.geonames.org/search.html?q={quote(query)}"
        await update.message.reply_text(
            f"לא נמצאו תוצאות בחיפוש אוטומטי. אפשר לחפש ידנית כאן:\n{url}\nלאחר שתמצאו מזהה, הגדירו: /setgeo <ID> [שם-מיקום]",
        )
        return
    chat_id = str(update.effective_chat.id)
    _search_cache_by_chat[chat_id] = {}
    keyboard = []
    for r in results:
        name = r.get('name') or ''
        country = r.get('countryName') or ''
        admin1 = r.get('adminName1') or ''
        gid = r.get('geonameId') or ''
        display = f"{name}, {country}{' · ' + admin1 if admin1 else ''} — {gid}"
        _search_cache_by_chat[chat_id][str(gid)] = f"{name}{' - ' + admin1 if admin1 else ''}"
        keyboard.append([InlineKeyboardButton(display, callback_data=f"setgeo:{gid}")])
    await update.message.reply_text(
        "בחרו מיקום מהרשימה:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cb_setgeo_from_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reporter.report_activity(update.effective_user.id)
    query = update.callback_query
    await query.answer()
    data = query.data or ''
    if not data.startswith('setgeo:'):
        return
    geoname_id = data.split(':', 1)[1].strip()
    # בדיקת אדמין
    if not await is_admin(update, context):
        await query.edit_message_text("⛔ רק אדמינים יכולים להגדיר מיקום.")
        return
    chat_id = query.message.chat_id
    key = str(chat_id)
    # ברירות מחדל
    g = _get_group_config(chat_id) or {
        'chat_id': key,
        'candle_lighting_offset': config.CANDLE_LIGHTING_OFFSET,
        'havdalah_offset': config.HAVDALAH_OFFSET,
        'lock_message': config.LOCK_MESSAGE,
        'unlock_message': config.UNLOCK_MESSAGE,
    }
    # שם מיקום לתצוגה מתוך המטמון (אם קיים)
    location_name = _search_cache_by_chat.get(key, {}).get(str(geoname_id)) or 'Custom'
    g.update({'geoname_id': geoname_id, 'location': location_name})
    _storage_cache[key] = g
    _save_storage()
    # ניקוי מקשים אינליין והודעת הצלחה
    try:
        await query.edit_message_reply_markup(None)
    except Exception:
        pass
    await context.bot.send_message(chat_id=chat_id, text=f"✅ הוגדר מיקום לקבוצה זו: {location_name} (GeoName: {geoname_id})")
    schedule_shabbat()


async def main():
    """
    פונקציה ראשית - מפעילה את הבוט
    """
    global application
    
    try:
        logger.info("🚀 מפעיל את בוט 'שומר שבת'...")
        
        # יצירת האפליקציה
        application = Application.builder().token(config.BOT_TOKEN).build()
        
        # טעינת אחסון
        _load_storage()

        # רישום handlers לפקודות
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("menu", cmd_menu))
        application.add_handler(CommandHandler("times", cmd_times))
        application.add_handler(CommandHandler("status", cmd_status))
        application.add_handler(CommandHandler("settings", cmd_settings))
        application.add_handler(CommandHandler("setgeo", cmd_setgeo))
        application.add_handler(CommandHandler("setoffsets", cmd_setoffsets))
        application.add_handler(CommandHandler("setmessages", cmd_setmessages))
        application.add_handler(CommandHandler("lock", cmd_lock))
        application.add_handler(CommandHandler("unlock", cmd_unlock))
        application.add_handler(CommandHandler("findgeo", cmd_findgeo))
        application.add_handler(CommandHandler("help", cmd_help))
        application.add_handler(CommandHandler("admin_help", cmd_admin_help))
        application.add_handler(CallbackQueryHandler(cb_setgeo_from_inline, pattern=r"^setgeo:\d+$"))
        # רישום error handler גלובלי
        application.add_error_handler(error_handler)
        
        # בדיקת חיבור לבוט
        me = await application.bot.get_me()
        logger.info(f"✅ מחובר כ: @{me.username}")

        # רישום רשימת הפקודות בטלגרם (כדי שיופיעו בתפריט /)
        await application.bot.set_my_commands([
            BotCommand("start", "ברוכים הבאים ומידע"),
            BotCommand("menu", "הצגת כפתורי הפקודות"),
            BotCommand("times", "זמני השבת הקרובה"),
            BotCommand("status", "סטטוס ותזמונים"),
            BotCommand("help", "עזרה"),
            BotCommand("lock", "נעילה (אדמין)"),
            BotCommand("unlock", "פתיחה (אדמין)"),
            BotCommand("settings", "הגדרות (אדמין)"),
            BotCommand("admin_help", "עזרה לאדמין"),
            BotCommand("setgeo", "הגדרת מיקום (אדמין)"),
            BotCommand("setoffsets", "עדכון הדלקה/הבדלה (אדמין)"),
            BotCommand("setmessages", "עדכון הודעות (אדמין)"),
            BotCommand("findgeo", "חיפוש מיקום לפי שם (אדמין)"),
        ])
        
        # התחלת הסקדיולר
        scheduler.start()
        logger.info("✅ Scheduler הופעל")
        
        # תזמון זמני השבת הראשונים
        schedule_shabbat()
        
        logger.info("✅ הבוט פעיל! ממתין לזמני שבת...")
        
        # התחלת הבוט (polling)
        await application.initialize()
        await application.start()
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
        
        # שמירה על הבוט פעיל
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("🛑 עוצר את הבוט...")
        scheduler.shutdown()
        if application:
            await application.stop()
            await application.shutdown()
        logger.info("👋 הבוט נעצר")
    except Exception as e:
        logger.error(f"❌ שגיאה קריטית: {e}")
        scheduler.shutdown()
        if application:
            await application.stop()
            await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
