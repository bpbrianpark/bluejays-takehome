from __future__ import annotations

import logging

from flask import Blueprint, current_app, render_template

from app.services.landing_data import load_leaderboard_page

logger = logging.getLogger(__name__)

leaders_bp = Blueprint("leaders", __name__)


@leaders_bp.route("/leaders")
def leaders():
    app = current_app
    leaders_error: str | None = None
    try:
        ctx = load_leaderboard_page(app)
    except (KeyError, TypeError, ValueError) as exc:
        logger.exception("Leaderboard configuration or load failed")
        leaders_error = str(exc)
        ctx = {
            "season_val": None,
            "hitting_blocks": [],
            "pitching_blocks": [],
            "row_limit": int(app.config.get("LEADERBOARD_ROW_LIMIT") or 15),
        }

    return render_template(
        "pages/leaders.html",
        **ctx,
        leaders_error=leaders_error,
    )
