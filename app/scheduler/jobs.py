"""MRUDA — Scheduler Jobs.

APScheduler daily job that runs the analysis pipeline at the configured hour.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.database import get_session
from app.analyzer.pipeline import run_analysis
from app.core.logging import get_logger

logger = get_logger("scheduler")

scheduler = AsyncIOScheduler()


async def daily_analysis_job():
    """Run the full analysis pipeline for yesterday's data."""
    logger.info("Scheduled daily analysis starting...")
    try:
        session = next(get_session())
        insight = await run_analysis(
            session=session,
            date_range="yesterday",
        )
        logger.info(
            f"Scheduled analysis complete. Confidence: {insight.confidence_score}"
        )
    except Exception as e:
        logger.error(f"Scheduled analysis failed: {e}")


def start_scheduler():
    """Configure and start the scheduler."""
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled via config")
        return

    scheduler.add_job(
        daily_analysis_job,
        "cron",
        hour=settings.analysis_hour,
        minute=0,
        id="daily_analysis",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info(f"Scheduler started. Daily analysis at {settings.analysis_hour}:00 UTC")


def stop_scheduler():
    """Shutdown the scheduler gracefully."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
