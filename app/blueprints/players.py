from __future__ import annotations

from flask import Blueprint, abort, current_app, render_template

from app.services.landing_data import team_logo_url
from app.services.player_page import load_player_page

players_bp = Blueprint("players", __name__)


@players_bp.route("/players/<int:player_id>")
def player_detail(player_id: int):
    app = current_app
    ctx = load_player_page(app, player_id)
    if ctx is None:
        abort(404)

    return render_template(
        "pages/player.html",
        **ctx,
        team_logo_url=team_logo_url,
    )
