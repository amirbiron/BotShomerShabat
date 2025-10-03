"""
בוט "שומר שבת" לטלגרם
נועל את הקבוצה בכניסת שבת ופותח בצאת השבת
"""
import asyncio
import logging
from datetime import datetime
from telegram import Update, Bot, ChatPermissions
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import config
from shabbat_times import get_next_shabbat_times

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


async def lock_group(context: ContextTypes.DEFAULT_TYPE = None):
    """
    נועל את הקבוצה - מאפשר רק לאדמינים לשלוח הודעות
    """
    try:
        logger.info(f"🔒 נועל את הקבוצה {config.CHAT_ID}")
        
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
            chat_id=config.CHAT_ID,
            permissions=permissions
        )
        
        # שליחת הודעה לקבוצה
        await bot.send_message(
            chat_id=config.CHAT_ID,
            text=config.LOCK_MESSAGE
        )
        
        logger.info("✅ הקבוצה ננעלה בהצלחה!")
        
    except TelegramError as e:
        logger.error(f"❌ שגיאה בנעילת הקבוצה: {e}")


async def unlock_group(context: ContextTypes.DEFAULT_TYPE = None):
    """
    פותח את הקבוצה - מאפשר לכולם לשלוח הודעות
    """
    try:
        logger.info(f"🔓 פותח את הקבוצה {config.CHAT_ID}")
        
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
            chat_id=config.CHAT_ID,
            permissions=permissions
        )
        
        # שליחת הודעה לקבוצה
        await bot.send_message(
            chat_id=config.CHAT_ID,
            text=config.UNLOCK_MESSAGE
        )
        
        logger.info("✅ הקבוצה נפתחה בהצלחה!")
        
    except TelegramError as e:
        logger.error(f"❌ שגיאה בפתיחת הקבוצה: {e}")


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
    
    times = get_next_shabbat_times()
    
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

📍 מיקום: {config.LOCATION}
    """
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /status - סטטוס הבוט
    """
    # בדיקת תזמונים קיימים
    lock_job = scheduler.get_job('lock_shabbat')
    unlock_job = scheduler.get_job('unlock_shabbat')
    refresh_job = scheduler.get_job('weekly_refresh')
    
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
    
    msg += f"\n📍 מיקום: {config.LOCATION}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /settings - הצגת הגדרות (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    msg = f"""
⚙️ **הגדרות הבוט**

📍 **מיקום:** {config.LOCATION}
🆔 **GeoName ID:** {config.GEONAME_ID}

⏰ **זמנים:**
• הדלקת נרות: {config.CANDLE_LIGHTING_OFFSET} דקות לפני שקיעה
• הבדלה: {config.HAVDALAH_OFFSET if config.HAVDALAH_OFFSET > 0 else 'אוטומטי (3 כוכבים)'}

💬 **הודעות:**
• נעילה: {config.LOCK_MESSAGE}
• פתיחה: {config.UNLOCK_MESSAGE}
    """
    await update.message.reply_text(msg, parse_mode='Markdown')


async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /lock - נעילה ידנית (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    await update.message.reply_text("🔒 נועל את הקבוצה...")
    await lock_group(context)
    await update.message.reply_text("✅ הקבוצה ננעלה!")


async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    פקודת /unlock - פתיחה ידנית (אדמין בלבד)
    """
    if not await is_admin(update, context):
        await update.message.reply_text("⛔ פקודה זו זמינה רק לאדמינים של הקבוצה.")
        return
    
    await update.message.reply_text("🔓 פותח את הקבוצה...")
    await unlock_group(context)
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
    מתזמן את נעילת ופתיחת הקבוצה לפי זמני השבת
    """
    logger.info("📅 מתזמן את זמני השבת הקרובה...")
    
    # משיכת זמני שבת
    times = get_next_shabbat_times()
    
    if not times:
        logger.error("❌ לא הצלחתי למשוך זמני שבת. ננסה שוב בעוד שעה.")
        # תזמון ניסיון חוזר בעוד שעה
        scheduler.add_job(
            schedule_shabbat,
            DateTrigger(run_date=datetime.now().replace(microsecond=0) + 
                       asyncio.get_event_loop().create_task(asyncio.sleep(3600)).result()),
            id='retry_schedule'
        )
        return
    
    candle_lighting = times['candle_lighting']
    havdalah = times['havdalah']
    
    # הסרת תזמונים קיימים (אם יש)
    for job_id in ['lock_shabbat', 'unlock_shabbat']:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
    
    # תזמון נעילה בכניסת שבת
    scheduler.add_job(
        lock_group,
        DateTrigger(run_date=candle_lighting),
        id='lock_shabbat'
    )
    logger.info(f"⏰ תוזמן נעילה: {candle_lighting.strftime('%Y-%m-%d %H:%M')}")
    
    # תזמון פתיחה בצאת השבת
    scheduler.add_job(
        unlock_group,
        DateTrigger(run_date=havdalah),
        id='unlock_shabbat'
    )
    logger.info(f"⏰ תוזמן פתיחה: {havdalah.strftime('%Y-%m-%d %H:%M')}")
    
    # תזמון רענון שבועי (ביום ראשון בלילה)
    next_refresh = havdalah.replace(hour=23, minute=0, second=0, microsecond=0)
    scheduler.add_job(
        schedule_shabbat,
        DateTrigger(run_date=next_refresh),
        id='weekly_refresh'
    )
    logger.info(f"🔄 רענון שבועי יתבצע ב: {next_refresh.strftime('%Y-%m-%d %H:%M')}")


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
