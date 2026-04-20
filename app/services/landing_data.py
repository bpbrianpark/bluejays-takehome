from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from flask import Flask

from app.services.mlb_stats import fetch_json

logger = logging.getLogger(__name__)

_LEADER_STAT_GROUP: dict[str, str] = {
    "homeRuns": "hitting",
    "runs": "hitting",
    "rbi": "hitting",
    "hits": "hitting",
    "battingAverage": "hitting",
    "onBasePlusSlugging": "hitting",
    "stolenBases": "hitting",
    "strikeouts": "pitching",
    "earnedRunAverage": "pitching",
    "wins": "pitching",
    "saves": "pitching",
    "whip": "pitching",
}

_LEADER_LABELS: dict[str, str] = {
    "homeRuns": "Home Runs",
    "runs": "Runs",
    "rbi": "RBI",
    "hits": "Hits",
    "battingAverage": "AVG",
    "onBasePlusSlugging": "OPS",
    "stolenBases": "Stolen Bases",
    "strikeouts": "Strikeouts",
    "earnedRunAverage": "ERA",
    "wins": "Wins",
    "saves": "Saves",
    "whip": "WHIP",
}


def team_logo_url(team_id: int) -> str:
    return f"https://www.mlbstatic.com/team-logos/{team_id}.svg"


def player_headshot_url(player_id: int, *, width: int = 96) -> str:
    return (
        "https://img.mlbstatic.com/mlb-photos/image/upload/"
        f"d_people:generic:headshot:silo:current.png/w_{width},q_auto:good,f_auto/"
        f"v1/people/{player_id}/headshot/silo/current"
    )


def default_stats_season() -> int:
    return dt.date.today().year


def _last_ten_record(team_record: dict[str, Any]) -> str:
    splits = ((team_record.get("records") or {}).get("splitRecords")) or []
    for split in splits:
        if str(split.get("type") or "").lower() != "lastten":
            continue
        w_l = split.get("wins")
        l_losses = split.get("losses")
        if w_l is not None and l_losses is not None:
            return f"{int(w_l)}-{int(l_losses)}"
    return "—"


def _format_run_differential(team_record: dict[str, Any]) -> str:
    rd = team_record.get("runDifferential")
    if rd is None:
        return "—"
    try:
        n = int(rd)
    except (TypeError, ValueError):
        return "—"
    if n > 0:
        return f"+{n}"
    return str(n)


def _split_pct(team_record: dict[str, Any], split_type: str) -> str:
    want = split_type.casefold()
    splits = ((team_record.get("records") or {}).get("splitRecords")) or []
    for split in splits:
        if str(split.get("type") or "").casefold() != want:
            continue
        p = split.get("pct")
        if p is not None and str(p).strip():
            return str(p).strip()
        return "—"
    return "—"


def _division_header_label(div: dict[str, Any]) -> str:
    short = div.get("nameShort")
    if short:
        return str(short)
    name = str(div.get("name") or "")
    return (
        name.replace("American League", "AL")
        .replace("National League", "NL")
        .strip()
    )


def load_division_headers(app: Flask) -> dict[int, str]:
    data = fetch_json("/divisions", params={"sportId": 1}, app=app)
    divisions = data.get("divisions") or []
    out: dict[int, str] = {}
    for d in divisions:
        if d.get("id") is None:
            continue
        out[int(d["id"])] = _division_header_label(d)
    return out


def load_standings_sections(app: Flask, *, include_split_pcts: bool = False) -> list[dict[str, Any]]:
    data = fetch_json(
        "/standings",
        params={"leagueId": "103,104", "hydrate": "team"},
        app=app,
    )
    records = data.get("records") or []
    try:
        div_headers = load_division_headers(app)
    except RuntimeError:
        logger.warning("Division headers unavailable; using division ids only.")
        div_headers = {}

    def sort_key(rec: dict[str, Any]) -> tuple[int, int]:
        league_id = int((rec.get("league") or {}).get("id") or 0)
        div_id = int((rec.get("division") or {}).get("id") or 0)
        return league_id, div_id

    sections: list[dict[str, Any]] = []
    for rec in sorted(records, key=sort_key):
        div_info = rec.get("division") or {}
        div_id = int(div_info["id"]) if div_info.get("id") is not None else None
        if div_id is not None and div_id in div_headers:
            division_name = div_headers[div_id]
        elif div_id is not None:
            division_name = f"Division {div_id}"
        else:
            division_name = "Division"

        teams_out: list[dict[str, Any]] = []
        for tr in sorted(
            rec.get("teamRecords") or [],
            key=lambda x: int(x.get("divisionRank") or 999),
        ):
            team = tr.get("team") or {}
            pct = str(tr.get("winningPercentage") or "")
            gb = str(tr.get("gamesBack") or "")
            tid = int(team["id"]) if team.get("id") is not None else None
            abbr = str(team.get("abbreviation") or team.get("teamCode") or "").upper()
            if not abbr:
                abbr = str(team.get("name") or "")[:3].upper()
            row: dict[str, Any] = {
                "name": abbr or str(team.get("name") or ""),
                "w": int(tr.get("wins") or 0),
                "l": int(tr.get("losses") or 0),
                "pct": pct if pct else "",
                "gb": gb if gb != "" else "—",
                "l10": _last_ten_record(tr),
                "diff": _format_run_differential(tr),
                "team_id": tid,
                "logo_url": team_logo_url(tid) if tid is not None else "",
            }
            if include_split_pcts:
                row["home_pct"] = _split_pct(tr, "home")
                row["away_pct"] = _split_pct(tr, "away")
                row["one_run_pct"] = _split_pct(tr, "oneRun")
                row["extra_inning_pct"] = _split_pct(tr, "extraInning")
            teams_out.append(row)

        sections.append({"division_name": division_name, "teams": teams_out})

    return sections


def _person_last_first(person: dict[str, Any]) -> str:
    """Display name as Last, First (matches player profile hero)."""
    lf = str(person.get("lastFirstName") or "").strip()
    if lf:
        return lf
    last = str(person.get("lastName") or "").strip()
    first = str(person.get("firstName") or "").strip()
    if last and first:
        return f"{last}, {first}"
    return str(person.get("fullName") or "").strip()


def _pick_leader_block(
    league_leaders: list[dict[str, Any]],
    *,
    category: str,
    preferred_group: str | None,
) -> dict[str, Any] | None:
    if preferred_group:
        for block in league_leaders:
            if str(block.get("statGroup") or "").lower() == preferred_group.lower():
                return block
    return league_leaders[0] if league_leaders else None


def load_leader_category(
    app: Flask,
    category: str,
    *,
    season: int | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    season_val = season if season is not None else default_stats_season()
    preferred = _LEADER_STAT_GROUP.get(category)

    params: dict[str, Any] = {
        "leaderCategories": category,
        "season": season_val,
        "limit": limit,
        "hydrate": "team",
    }

    try:
        data = fetch_json("/stats/leaders", params=params, app=app)
    except RuntimeError as exc:
        logger.warning("Leader fetch failed for %s: %s", category, exc)
        return {
            "category": category,
            "label": _LEADER_LABELS.get(category, category.replace("_", " ").title()),
            "season": season_val,
            "rows": [],
            "error": str(exc),
        }

    league_leaders = data.get("leagueLeaders") or []
    block = _pick_leader_block(league_leaders, category=category, preferred_group=preferred)

    rows: list[dict[str, Any]] = []
    if block:
        for entry in (block.get("leaders") or [])[:limit]:
            person = entry.get("person") or {}
            team = entry.get("team") or {}
            pid = int(person["id"]) if person.get("id") is not None else None
            abbr = str(team.get("abbreviation") or team.get("teamCode") or "").upper()
            if not abbr and team.get("name"):
                abbr = str(team.get("name"))[:4].upper()
            rows.append(
                {
                    "rank": entry.get("rank"),
                    "player": _person_last_first(person),
                    "team": str(team.get("name") or ""),
                    "team_abbr": abbr or "—",
                    "value": str(entry.get("value") or ""),
                    "player_id": pid,
                    "headshot_url": player_headshot_url(pid) if pid is not None else "",
                }
            )

    return {
        "category": category,
        "label": _LEADER_LABELS.get(category, category.replace("_", " ").title()),
        "season": season_val,
        "rows": rows,
        "error": None,
    }


def load_all_leader_categories(
    app: Flask,
    categories: tuple[str, ...] | None = None,
    *,
    season: int | None = None,
    leader_limit: int = 1,
) -> list[dict[str, Any]]:
    cats = categories or app.config["LANDING_LEADER_CATEGORIES"]
    out: list[dict[str, Any]] = []
    for cat in cats:
        out.append(load_leader_category(app, cat, season=season, limit=leader_limit))
    return out


def load_leaderboard_page(
    app: Flask,
    *,
    season: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Load hitting and pitching leader blocks for the full leaderboards page."""
    season_val = season if season is not None else default_stats_season()
    row_limit = limit if limit is not None else int(app.config.get("LEADERBOARD_ROW_LIMIT") or 15)
    hitting_cats: tuple[str, ...] = tuple(app.config["LEADERBOARD_HITTING_CATEGORIES"])
    pitching_cats: tuple[str, ...] = tuple(app.config["LEADERBOARD_PITCHING_CATEGORIES"])

    hitting_blocks = [
        load_leader_category(app, cat, season=season_val, limit=row_limit) for cat in hitting_cats
    ]
    pitching_blocks = [
        load_leader_category(app, cat, season=season_val, limit=row_limit) for cat in pitching_cats
    ]

    return {
        "season_val": season_val,
        "hitting_blocks": hitting_blocks,
        "pitching_blocks": pitching_blocks,
        "row_limit": row_limit,
    }
