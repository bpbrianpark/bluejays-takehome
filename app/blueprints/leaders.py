from flask import Blueprint, render_template

leaders_bp = Blueprint("leaders", __name__)


@leaders_bp.route("/leaders")
def leaders():
    return render_template("pages/leaders.html")
