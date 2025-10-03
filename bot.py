"""
בוט "שומר שבת" לטלגרם
נועל את הקבוצה בכניסת שבת ופותח בצאת השבת
"""
import asyncio
import logging
from datetime import datetime
from telegram import Bot, ChatPermissions
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

# אתחול הבוט והסקדיולר
bot = Bot(token=config.BOT_TOKEN)
scheduler = AsyncIOScheduler()


async def lock_group():
    """
    נועל את הקבוצה - מאפשר רק לאדמינים לשלוח הודעות
    """
    try:
        logger.info(f"🔒 נועל את הקבוצה {config.CHAT_ID}")
        
        # הרשאות מוגבלות - רק אדמינים יכולים לשלוח
        permissions = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
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


async def unlock_group():
    """
    פותח את הקבוצה - מאפשר לכולם לשלוח הודעות
    """
    try:
        logger.info(f"🔓 פותח את הקבוצה {config.CHAT_ID}")
        
        # הרשאות מלאות - כולם יכולים לשלוח
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
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
    try:
        logger.info("🚀 מפעיל את בוט 'שומר שבת'...")
        
        # בדיקת חיבור לבוט
        me = await bot.get_me()
        logger.info(f"✅ מחובר כ: @{me.username}")
        
        # התחלת הסקדיולר
        scheduler.start()
        logger.info("✅ Scheduler הופעל")
        
        # תזמון זמני השבת הראשונים
        schedule_shabbat()
        
        logger.info("✅ הבוט פעיל! ממתין לזמני שבת...")
        
        # שמירה על הבוט פעיל
        while True:
            await asyncio.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("🛑 עוצר את הבוט...")
        scheduler.shutdown()
        logger.info("👋 הבוט נעצר")
    except Exception as e:
        logger.error(f"❌ שגיאה קריטית: {e}")
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
