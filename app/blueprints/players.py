from flask import Blueprint, render_template

players_bp = Blueprint("players", __name__)


@players_bp.route("/players/<int:player_id>")
def player_detail(player_id: int):
    return render_template("pages/player.html")
