from flask import Blueprint, render_template

teams_bp = Blueprint("teams", __name__)


@teams_bp.route("/teams/<int:team_id>")
def team_detail(team_id: int):
    return render_template("pages/team.html")
