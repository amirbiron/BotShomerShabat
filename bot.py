"""
בוט "שומר שבת" לטלגרם
נועל את הקבוצה בכניסת שבת ופותח בצאת השבת
"""
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, Bot, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import config
from shabbat_times import get_next_shabbat_times, get_next_shabbat_times_for

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


def _to_int_chat_id(chat_id: str | int) -> int:
    try:
        return int(chat_id)
    except Exception:
        # בטלגרם chat_id יכול להיות מחרוזת; ננסה להסיר רווחים וסימנים לא נחוצים
        return int(str(chat_id).strip())


def _get_group_config(chat_id: int | str) -> dict | None:
    for g in config.GROUPS:
        if str(g['chat_id']) == str(chat_id):
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
    welcome_msg = """
🕯️ **ברוך הבא לבוט "שומר שבת"!**

אני בוט אוטומטי שנועל את הקבוצה בכניסת שבת ופותח אותה בצאת השבת.

📋 **פקודות זמינות:**
/times - הצגת זמני השבת הקרובה
/status - סטטוס הבוט והתזמונים
/help - עזרה ומידע

🔐 **פקודות אדמין בלבד:**
/lock - נעילה ידנית של הקבוצה
/unlock - פתיחה ידנית של הקבוצה
/settings - הצגת ההגדרות

✨ הבוט פועל אוטומטית - אין צורך לעשות דבר!
    """
    await update.message.reply_text(welcome_msg, parse_mode='Markdown')


async def cmd_times(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /times - הצגת זמני שבת
    """
    await update.message.reply_text("🔍 מושך זמני שבת...")
    
    # זיהוי הקבוצה הנוכחית לפי ההודעה
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or config.GROUPS[0]
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
    
    g = _get_group_config(chat_id) or config.GROUPS[0]
    msg += f"\n📍 מיקום: {g['location']}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /settings - הצגת הגדרות (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or config.GROUPS[0]
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


async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /lock - נעילה ידנית (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or config.GROUPS[0]
    await update.message.reply_text("🔒 נועל את הקבוצה...")
    await lock_group_for(g['chat_id'], g['lock_message'], context)
    await update.message.reply_text("✅ הקבוצה ננעלה!")


async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /unlock - פתיחה ידנית (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    chat_id = update.effective_chat.id
    g = _get_group_config(chat_id) or config.GROUPS[0]
    await update.message.reply_text("🔓 פותח את הקבוצה...")
    await unlock_group_for(g['chat_id'], g['unlock_message'], context)
    await update.message.reply_text("✅ הקבוצה נפתחה!")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /help - עזרה
    """
    help_msg = """
🕯️ **עזרה - בוט שומר שבת**

**מה הבוט עושה?**
הבוט נועל את הקבוצה אוטומטית בזמן הדלקת נרות ופותח אותה בזמן הבדלה.

📋 **פקודות כלליות:**
• /times - הצגת זמני השבת הקרובה
• /status - סטטוס הבוט והתזמונים הקרובים
• /help - הודעת עזרה זו

🔐 **פקודות אדמין:**
• /lock - נעילה ידנית של הקבוצה
• /unlock - פתיחה ידנית של הקבוצה
• /settings - הצגת הגדרות הבוט

❓ **שאלות נפוצות:**

**איך הבוט יודע את זמני השבת?**
הבוט משתמש ב-Hebcal API ומושך את הזמנים לפי המיקום שהוגדר.

**מה אם זמני השבת לא מדויקים?**
ניתן לשנות את ההגדרות (מיקום, דקות לפני/אחרי) במשתני הסביבה.

**האם הבוט פועל גם בחגים?**
כרגע הבוט פועל רק בשבת. תמיכה בחגים תתווסף בעתיד.

✨ נתקלת בבעיה? פנה למפתח הבוט.
    """
    await update.message.reply_text(help_msg, parse_mode='Markdown')


def schedule_shabbat():
    """
    מתזמן את נעילת ופתיחת הקבוצות לפי זמני השבת עבור כל קבוצה
    """
    logger.info("📅 מתזמן את זמני השבת הקרובה לכל הקבוצות...")

    for g in config.GROUPS:
        gid = str(g['chat_id'])

        # משיכת זמני שבת עבור הקבוצה
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


async def main():
    """
    פונקציה ראשית - מפעילה את הבוט
    """
    global application
    
    try:
        logger.info("🚀 מפעיל את בוט 'שומר שבת'...")
        
        # יצירת האפליקציה
        application = Application.builder().token(config.BOT_TOKEN).build()
        
        # רישום handlers לפקודות
        application.add_handler(CommandHandler("start", cmd_start))
        application.add_handler(CommandHandler("times", cmd_times))
        application.add_handler(CommandHandler("status", cmd_status))
        application.add_handler(CommandHandler("settings", cmd_settings))
        application.add_handler(CommandHandler("lock", cmd_lock))
        application.add_handler(CommandHandler("unlock", cmd_unlock))
        application.add_handler(CommandHandler("help", cmd_help))
        # רישום error handler גלובלי
        application.add_error_handler(error_handler)
        
        # בדיקת חיבור לבוט
        me = await application.bot.get_me()
        logger.info(f"✅ מחובר כ: @{me.username}")
        
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
