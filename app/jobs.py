"""
app/jobs.py - Daily Scheduler Registration for Telegram JobQueue.

Registers daily broadcast job at configured local time (Asia/Phnom_Penh).
Verifies JobQueue availability and logs actionable error if missing.
"""

import logging
from datetime import time
import pytz
from telegram.ext import Application, ContextTypes

from app.storage import Storage
from ai_service import AIService
from app.services.broadcast import send_daily_broadcast

logger = logging.getLogger(__name__)

def register_daily_job(
    application: Application,
    storage: Storage,
    ai: AIService,
    daily_time_str: str = "08:00",
    timezone_str: str = "Asia/Phnom_Penh",
):
    """Registers the daily broadcast callback in Telegram JobQueue."""
    if not application.job_queue:
        logger.error(
            "CRITICAL: JobQueue is NOT available on this Telegram Application instance. "
            "Daily scheduled broadcasts will NOT run! "
            "Ensure python-telegram-bot is installed with job-queue extra: "
            "pip install \"python-telegram-bot[job-queue]\""
        )
        return

    try:
        parts = daily_time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        tz = pytz.timezone(timezone_str)
        scheduled_time = time(hour=hour, minute=minute, tzinfo=tz)

        async def _job_callback(context: ContextTypes.DEFAULT_TYPE):
            await send_daily_broadcast(context.bot, storage, ai)

        application.job_queue.run_daily(_job_callback, time=scheduled_time)
        logger.info(f"Daily broadcast job successfully registered at {daily_time_str} ({timezone_str})")
    except Exception as e:
        logger.error(f"Failed to register daily broadcast job: {e}")
