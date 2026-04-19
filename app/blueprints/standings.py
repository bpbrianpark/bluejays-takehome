from flask import Blueprint, render_template

standings_bp = Blueprint("standings", __name__)


@standings_bp.route("/standings")
def standings():
    return render_template("pages/standings.html")
