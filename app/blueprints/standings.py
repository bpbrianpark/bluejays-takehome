import logging

from flask import Blueprint, current_app, render_template

from app.services.landing_data import load_standings_sections

logger = logging.getLogger(__name__)

standings_bp = Blueprint("standings", __name__)


@standings_bp.route("/standings")
def standings():
    app = current_app

    standings_sections: list = []
    standings_error: str | None = None
    try:
        standings_sections = load_standings_sections(app, include_split_pcts=True)
    except RuntimeError as exc:
        logger.exception("Standings load failed")
        standings_error = str(exc)

    return render_template(
        "pages/standings.html",
        standings_sections=standings_sections,
        standings_error=standings_error,
    )
