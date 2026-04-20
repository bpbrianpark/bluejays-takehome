from __future__ import annotations

import logging

from flask import Blueprint, abort, current_app, render_template

from app.services.landing_data import default_stats_season, team_logo_url
from app.services.news_rss import fetch_news_items
from app.services.team_page import (
    BATTING_STAT_COLUMNS,
    PITCHING_STAT_COLUMNS,
    build_batting_rows,
    build_pitching_rows,
    build_team_leader_blocks,
    fetch_people_stats_map,
    is_pitcher_entry,
    load_standings_snippet,
    load_team_record,
    load_team_roster_entries,
    mlb_com_team_news_rss_url,
    roster_age_fallback,
)

logger = logging.getLogger(__name__)

teams_bp = Blueprint("teams", __name__)


@teams_bp.route("/teams/<int:team_id>")
def team_detail(team_id: int):
    app = current_app

    raw_team = load_team_record(team_id, app=app)
    if raw_team is None:
        abort(404)

    team = {
        "id": team_id,
        "name": str(raw_team.get("name") or ""),
        "abbr": str(raw_team.get("abbreviation") or "").strip().upper(),
        "logo_url": team_logo_url(team_id),
    }

    standings = None
    standings_error: str | None = None
    try:
        standings = load_standings_snippet(app, team_id)
    except RuntimeError as exc:
        logger.exception("Team standings load failed")
        standings_error = str(exc)

    season_val = default_stats_season()
    batting_rows: list = []
    pitching_rows: list = []
    team_leader_blocks: list = []
    stats_error: str | None = None
    try:
        roster = load_team_roster_entries(app, team_id, season=season_val)
        person_ids = [
            int((e.get("person") or {})["id"])
            for e in roster
            if (e.get("person") or {}).get("id") is not None
        ]
        pitching_ids = [
            int((e.get("person") or {})["id"])
            for e in roster
            if is_pitcher_entry(e) and (e.get("person") or {}).get("id") is not None
        ]
        age_fb = roster_age_fallback(roster)
        hitting_map = fetch_people_stats_map(app, person_ids, season=season_val, group="hitting")
        pitching_map = fetch_people_stats_map(app, pitching_ids, season=season_val, group="pitching")
        batting_rows = build_batting_rows(roster, hitting_map, season_age_fallback=age_fb)
        pitching_rows = build_pitching_rows(roster, pitching_map, season_age_fallback=age_fb)
        team_leader_blocks = build_team_leader_blocks(
            roster,
            hitting_map,
            pitching_map,
            team_abbr=team["abbr"],
            categories=tuple(app.config["LANDING_LEADER_CATEGORIES"]),
        )
    except RuntimeError as exc:
        logger.exception("Team roster or stats load failed")
        stats_error = str(exc)

    news_items: list = []
    news_error: str | None = None
    try:
        news_items = fetch_news_items(app, rss_url=mlb_com_team_news_rss_url(raw_team), limit=12)
    except RuntimeError as exc:
        logger.exception("Team news RSS load failed")
        news_error = str(exc)

    return render_template(
        "pages/team.html",
        team=team,
        standings=standings,
        standings_error=standings_error,
        season_val=season_val,
        batting_stat_columns=BATTING_STAT_COLUMNS,
        batting_rows=batting_rows,
        pitching_stat_columns=PITCHING_STAT_COLUMNS,
        pitching_rows=pitching_rows,
        team_leader_blocks=team_leader_blocks,
        stats_error=stats_error,
        news_items=news_items,
        news_error=news_error,
    )
