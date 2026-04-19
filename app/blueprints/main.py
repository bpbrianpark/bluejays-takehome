import logging

from flask import Blueprint, current_app, render_template

from app.services.landing_data import load_all_leader_categories, load_standings_sections
from app.services.news_rss import fetch_news_items

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    app = current_app

    standings_sections: list = []
    standings_error: str | None = None
    try:
        standings_sections = load_standings_sections(app)
    except RuntimeError as exc:
        logger.exception("Standings load failed")
        standings_error = str(exc)

    news_items: list = []
    news_error: str | None = None
    try:
        news_items = fetch_news_items(app, limit=12)
    except RuntimeError as exc:
        logger.exception("News RSS load failed")
        news_error = str(exc)

    leader_blocks: list = []
    leaders_error: str | None = None
    try:
        leader_blocks = load_all_leader_categories(app, leader_limit=1)
    except RuntimeError as exc:
        logger.exception("Stat leaders load failed")
        leaders_error = str(exc)

    return render_template(
        "pages/index.html",
        standings_sections=standings_sections,
        standings_error=standings_error,
        news_items=news_items,
        news_error=news_error,
        leader_blocks=leader_blocks,
        leaders_error=leaders_error,
    )
