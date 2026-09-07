import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

import database
import scraper

logger = logging.getLogger("tracker.scheduler")

AUTO_REFRESH_HOURS = float(os.environ.get("AUTO_REFRESH_HOURS", 6))


def refresh_all_tracked():
    """The core of the 'fully automated' part: walk the watchlist and take
    a fresh view-count snapshot for every tracked game, unattended."""
    games = database.get_all_games()
    if not games:
        logger.info("No tracked games to refresh.")
        return

    session = scraper.get_session()
    for game in games:
        result = scraper.scrape_single_page(game["source"], game["url"], session)
        database.record_snapshot(game["id"], result["views"])
        logger.info("Refreshed '%s' (%s): %s views", game["title"], game["source"], result["views"])


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        refresh_all_tracked,
        "interval",
        hours=AUTO_REFRESH_HOURS,
        id="refresh_all_tracked",
        next_run_time=None,  # first run is scheduled AUTO_REFRESH_HOURS from now; trigger once manually if you want an immediate run
    )
    scheduler.start()
    logger.info("Scheduler started: refreshing every %s hour(s).", AUTO_REFRESH_HOURS)
    return scheduler
