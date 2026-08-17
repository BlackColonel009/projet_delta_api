from apscheduler.schedulers.background import BackgroundScheduler
from gotrue import User
from app.database import SessionLocal # ta fonction
import asyncio


from jinja2 import Environment, FileSystemLoader, select_autoescape

from io import BytesIO
import os

from app.repo_scheduler.scheduler_ai import run_followup_scheduler
from app.repo_scheduler.stock_alert_ai import run_stock_alert_scheduler
from app.config import settings
import logging



# TEMPLATES_DIR = os.path.join("app", "templates", "pdf")

logger = logging.getLogger(__name__)
_scheduler = None


def start_scheduler():
    global _scheduler

    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler désactivé par SCHEDULER_ENABLED=false")
        return None

    if _scheduler and _scheduler.running:
        return _scheduler

    scheduler = BackgroundScheduler()

    def scheduled_job():
        db = SessionLocal()
        try:
            asyncio.run(run_followup_scheduler(db))  # si async
        finally:
            db.close()

    def stock_alert_job():
        db = SessionLocal()
        try:
            asyncio.run(run_stock_alert_scheduler(db))  # ← à créer
        finally:
            db.close()

    scheduler.add_job(scheduled_job, "interval", minutes=1)
    scheduler.add_job(stock_alert_job, "interval", days=7)  # ⏰ toute les semaines
    scheduler.start()
    _scheduler = scheduler
    return scheduler



