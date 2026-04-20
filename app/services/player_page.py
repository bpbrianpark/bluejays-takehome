from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from flask import Flask

from app.services.landing_data import default_stats_season, player_headshot_url
from app.services.mlb_stats import fetch_json
from app.services.team_page import player_last_first

logger = logging.getLogger(__name__)

HITTING_CAREER_COLUMNS: list[dict[str, str]] = [
    {"key": "year", "label": "Year"},
    {"key": "team_abbr", "label": "Team"},
    {"key": "g", "label": "G"},
    {"key": "pa", "label": "PA"},
    {"key": "ab", "label": "AB"},
    {"key": "r", "label": "R"},
    {"key": "h", "label": "H"},
    {"key": "doubles", "label": "2B"},
    {"key": "triples", "label": "3B"},
    {"key": "hr", "label": "HR"},
    {"key": "rbi", "label": "RBI"},
    {"key": "bb", "label": "BB"},
    {"key": "so", "label": "SO"},
    {"key": "sb", "label": "SB"},
    {"key": "cs", "label": "CS"},
    {"key": "avg", "label": "AVG"},
    {"key": "obp", "label": "OBP"},
    {"key": "slg", "label": "SLG"},
    {"key": "ops", "label": "OPS"},
    {"key": "bb_pct", "label": "BB%"},
    {"key": "so_pct", "label": "SO%"},
]

PITCHING_CAREER_COLUMNS: list[dict[str, str]] = [
    {"key": "year", "label": "Year"},
    {"key": "team_abbr", "label": "Team"},
    {"key": "w", "label": "W"},
    {"key": "l", "label": "L"},
    {"key": "era", "label": "ERA"},
    {"key": "g", "label": "G"},
    {"key": "gs", "label": "GS"},
    {"key": "sv", "label": "SV"},
    {"key": "ip", "label": "IP"},
    {"key": "bf", "label": "BF"},
    {"key": "h", "label": "H"},
    {"key": "r", "label": "R"},
    {"key": "er", "label": "ER"},
    {"key": "hr", "label": "HR"},
    {"key": "bb", "label": "BB"},
    {"key": "so", "label": "SO"},
    {"key": "whip", "label": "WHIP"},
    {"key": "avg", "label": "AVG"},
    {"key": "bb_pct", "label": "BB%"},
    {"key": "so_pct", "label": "SO%"},
]

_MLB_SPORT_ID = 1


def _fmt_stat(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)
    s = str(val).strip()
    return s if s else "—"


def _fmt_pct_ratio(numerator: Any, denominator: Any) -> str:
    try:
        n = float(numerator)
        d = float(denominator)
        if d <= 0:
            return "—"
        return f"{100.0 * n / d:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _bb_so_pct_hitting(stat: dict[str, Any]) -> tuple[str, str]:
    pa = stat.get("plateAppearances")
    bb = stat.get("baseOnBalls")
    so = stat.get("strikeOuts")
    return (
        _fmt_pct_ratio(bb, pa),
        _fmt_pct_ratio(so, pa),
    )


def _bb_so_pct_pitching(stat: dict[str, Any]) -> tuple[str, str]:
    bf = stat.get("battersFaced")
    bb = stat.get("baseOnBalls")
    so = stat.get("strikeOuts")
    return (
        _fmt_pct_ratio(bb, bf),
        _fmt_pct_ratio(so, bf),
    )


def _filter_mlb_regular_splits(splits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sp in splits:
        if str(sp.get("gameType") or "R") != "R":
            continue
        sport = sp.get("sport") or {}
        sid = sport.get("id")
        if sid is not None and int(sid) != _MLB_SPORT_ID:
            continue
        out.append(sp)
    return out


def _season_sort_key_asc(sp: dict[str, Any]) -> tuple[int]:
    """Oldest season first (table reads chronologically down to newest, then projection, then totals)."""
    try:
        y = int(sp.get("season") or 0)
    except (TypeError, ValueError):
        y = 0
    return (y,)


def _fetch_team_abbr_map(app: Flask, team_ids: set[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    for tid in sorted(team_ids):
        if tid <= 0:
            continue
        try:
            data = fetch_json(f"/teams/{tid}", app=app)
            teams = data.get("teams") or []
            if teams:
                abbr = str(teams[0].get("abbreviation") or "").strip().upper()
                if abbr:
                    out[tid] = abbr
        except RuntimeError:
            logger.debug("Team %s abbreviation fetch failed", tid, exc_info=True)
    return out


def _split_team_id(team: dict[str, Any] | None) -> int | None:
    if not team:
        return None
    tid = team.get("id")
    if tid is None:
        return None
    try:
        return int(tid)
    except (TypeError, ValueError):
        return None


def _hydrate_game_log(group: str, season: int, start: str, end: str) -> str:
    return (
        f"stats(group=[{group}],type=[gameLog],season={season},"
        f"startDate={start},endDate={end})"
    )


def _merge_projection_after_season(
    season_rows: list[dict[str, Any]],
    proj_row: dict[str, Any] | None,
    season_val: int,
) -> list[dict[str, Any]]:
    """Insert projection after the ``season_val`` year row if present; else after the latest season row.

    ``season_rows`` must be sorted **ascending** by season so the table ends with: …, latest year, Proj, Totals.
    """
    if not proj_row:
        out = list(season_rows)
        for r in out:
            r.pop("_season_key", None)
        return out
    merged: list[dict[str, Any]] = []
    inserted = False
    target = str(season_val)
    for row in season_rows:
        merged.append(row)
        if not inserted and row.get("_season_key") == target:
            merged.append(proj_row)
            inserted = True
    if not inserted:
        merged.append(proj_row)
    for r in merged:
        r.pop("_season_key", None)
    return merged


def _hitting_stat_row(
    *,
    kind: str,
    year_display: str,
    team_tid: int | None,
    team_abbr: str,
    stat: dict[str, Any],
    season_key: str | None = None,
) -> dict[str, Any]:
    bb_p, so_p = _bb_so_pct_hitting(stat)
    row: dict[str, Any] = {
        "kind": kind,
        "year": year_display,
        "team_id": team_tid,
        "team_abbr": team_abbr,
        "g": _fmt_stat(stat.get("gamesPlayed")),
        "pa": _fmt_stat(stat.get("plateAppearances")),
        "ab": _fmt_stat(stat.get("atBats")),
        "r": _fmt_stat(stat.get("runs")),
        "h": _fmt_stat(stat.get("hits")),
        "doubles": _fmt_stat(stat.get("doubles")),
        "triples": _fmt_stat(stat.get("triples")),
        "hr": _fmt_stat(stat.get("homeRuns")),
        "rbi": _fmt_stat(stat.get("rbi")),
        "bb": _fmt_stat(stat.get("baseOnBalls")),
        "so": _fmt_stat(stat.get("strikeOuts")),
        "sb": _fmt_stat(stat.get("stolenBases")),
        "cs": _fmt_stat(stat.get("caughtStealing")),
        "avg": _fmt_stat(stat.get("avg")),
        "obp": _fmt_stat(stat.get("obp")),
        "slg": _fmt_stat(stat.get("slg")),
        "ops": _fmt_stat(stat.get("ops")),
        "bb_pct": bb_p,
        "so_pct": so_p,
    }
    if season_key is not None:
        row["_season_key"] = season_key
    return row


def _pitching_stat_row(
    *,
    kind: str,
    year_display: str,
    team_tid: int | None,
    team_abbr: str,
    stat: dict[str, Any],
    season_key: str | None = None,
) -> dict[str, Any]:
    bb_p, so_p = _bb_so_pct_pitching(stat)
    row: dict[str, Any] = {
        "kind": kind,
        "year": year_display,
        "team_id": team_tid,
        "team_abbr": team_abbr,
        "w": _fmt_stat(stat.get("wins")),
        "l": _fmt_stat(stat.get("losses")),
        "era": _fmt_stat(stat.get("era")),
        "g": _fmt_stat(stat.get("gamesPlayed")),
        "gs": _fmt_stat(stat.get("gamesStarted")),
        "sv": _fmt_stat(stat.get("saves")),
        "ip": _fmt_stat(stat.get("inningsPitched")),
        "bf": _fmt_stat(stat.get("battersFaced")),
        "h": _fmt_stat(stat.get("hits")),
        "r": _fmt_stat(stat.get("runs")),
        "er": _fmt_stat(stat.get("earnedRuns")),
        "hr": _fmt_stat(stat.get("homeRuns")),
        "bb": _fmt_stat(stat.get("baseOnBalls")),
        "so": _fmt_stat(stat.get("strikeOuts")),
        "whip": _fmt_stat(stat.get("whip")),
        "avg": _fmt_stat(stat.get("avg")),
        "bb_pct": bb_p,
        "so_pct": so_p,
    }
    if season_key is not None:
        row["_season_key"] = season_key
    return row


def _has_meaningful_hitting(stat: dict[str, Any]) -> bool:
    try:
        return int(stat.get("plateAppearances") or 0) > 0 or int(stat.get("atBats") or 0) > 0
    except (TypeError, ValueError):
        return False


def _has_meaningful_pitching(stat: dict[str, Any]) -> bool:
    try:
        bf = int(stat.get("battersFaced") or 0)
        ip = str(stat.get("inningsPitched") or "").strip()
        return bf > 0 or bool(ip and ip not in {"", "0", "0.0"})
    except (TypeError, ValueError):
        return False


def _fmt_game_date(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        parsed = dt.date.fromisoformat(raw[:10])
        return f"{parsed.strftime('%b')} {parsed.day}, {parsed.year}"
    except ValueError:
        return raw


def _opp_display(
    opp: dict[str, Any] | None,
    abbr_map: dict[int, str],
) -> str:
    if not opp:
        return "—"
    oid = opp.get("id")
    if oid is not None:
        try:
            oi = int(oid)
            if oi in abbr_map:
                return abbr_map[oi]
        except (TypeError, ValueError):
            pass
    name = str(opp.get("name") or "").strip()
    return name if name else "—"


def _is_primary_pitcher(person: dict[str, Any]) -> bool:
    pos = person.get("primaryPosition") or {}
    return str(pos.get("code") or "") == "1"


def load_player_page(app: Flask, player_id: int) -> dict[str, Any] | None:
    """Return template context dict for the player profile, or ``None`` if player not found."""
    try:
        pdata = fetch_json(f"/people/{player_id}", params={"hydrate": "currentTeam"}, app=app)
    except RuntimeError:
        logger.exception("player fetch failed %s", player_id)
        return None

    people = pdata.get("people") or []
    if not people:
        return None

    person = people[0]
    season_val = default_stats_season()

    current_team = person.get("currentTeam") or {}
    current_tid = _split_team_id(current_team)
    team_name = str(current_team.get("name") or "").strip() or "—"

    pos = person.get("primaryPosition") or {}
    pos_abbr = str(pos.get("abbreviation") or "—").strip()

    throw = person.get("pitchHand") or {}
    throws = str(throw.get("code") or "—").strip()

    age_v = person.get("currentAge")
    age_s = _fmt_stat(age_v) if age_v is not None else "—"

    height = str(person.get("height") or "").strip() or "—"
    weight_v = person.get("weight")
    weight_s = f"{weight_v} lbs" if isinstance(weight_v, int) else _fmt_stat(weight_v)

    draft_raw = person.get("draftYear")
    try:
        draft_s = str(int(draft_raw)) if draft_raw is not None else "—"
    except (TypeError, ValueError):
        draft_s = "—"

    hero = {
        "name_last_first": player_last_first(person),
        "headshot_url": player_headshot_url(player_id, width=160),
        "position_abbr": pos_abbr,
        "team_name": team_name,
        "throws": throws,
        "age": age_s,
        "height": height,
        "weight": weight_s,
        "draft_year": draft_s,
    }

    stat_errors: list[str] = []
    hitting_block: dict[str, Any] | None = None
    pitching_block: dict[str, Any] | None = None

    try:
        yby_h = fetch_json(
            f"/people/{player_id}/stats",
            params={"stats": "yearByYear", "group": "hitting"},
            app=app,
        )
        car_h = fetch_json(
            f"/people/{player_id}/stats",
            params={"stats": "careerRegularSeason", "group": "hitting"},
            app=app,
        )
        pr_h = fetch_json(
            f"/people/{player_id}/stats",
            params={
                "stats": "projected",
                "group": "hitting",
                "season": season_val,
            },
            app=app,
        )

        yby_splits = _filter_mlb_regular_splits((yby_h.get("stats") or [{}])[0].get("splits") or [])
        yby_splits.sort(key=_season_sort_key_asc)

        car_splits = (car_h.get("stats") or [{}])[0].get("splits") or []
        career_stat_h = (car_splits[0].get("stat") if car_splits else {}) or {}

        proj_splits = (pr_h.get("stats") or [{}])[0].get("splits") or []
        proj_stat = (proj_splits[0].get("stat") if proj_splits else None) or None

        want_hitting = (
            bool(yby_splits)
            or _has_meaningful_hitting(career_stat_h)
            or bool(proj_stat)
        )

        if want_hitting:
            team_ids: set[int] = set()
            for sp in yby_splits:
                tid = _split_team_id(sp.get("team"))
                if tid:
                    team_ids.add(tid)
            for sp in car_splits:
                tid = _split_team_id(sp.get("team"))
                if tid:
                    team_ids.add(tid)
            if current_tid:
                team_ids.add(current_tid)
            abbr_map = _fetch_team_abbr_map(app, team_ids)

            season_rows: list[dict[str, Any]] = []
            for sp in yby_splits:
                st = sp.get("stat") or {}
                tid = _split_team_id(sp.get("team"))
                abbr = abbr_map.get(tid, "—") if tid else "—"
                sk = str(sp.get("season") or "")
                season_rows.append(
                    _hitting_stat_row(
                        kind="season",
                        year_display=sk,
                        team_tid=tid,
                        team_abbr=abbr,
                        stat=st,
                        season_key=sk,
                    )
                )

            proj_row = None
            if proj_stat:
                ptid = current_tid
                pabbr = abbr_map.get(ptid, "—") if ptid else "—"
                proj_row = _hitting_stat_row(
                    kind="projection",
                    year_display="Proj",
                    team_tid=ptid,
                    team_abbr=pabbr,
                    stat=proj_stat,
                )

            body_rows = _merge_projection_after_season(season_rows, proj_row, season_val)

            if car_splits or _has_meaningful_hitting(career_stat_h):
                ctid = _split_team_id(car_splits[0].get("team")) if car_splits else None
                cabbr = abbr_map.get(ctid, "—") if ctid else "—"
                body_rows.append(
                    _hitting_stat_row(
                        kind="career",
                        year_display="Totals",
                        team_tid=ctid,
                        team_abbr=cabbr,
                        stat=career_stat_h,
                    )
                )

            hitting_block = {
                "title": "Batting",
                "columns": HITTING_CAREER_COLUMNS,
                "rows": body_rows,
            }
    except RuntimeError as exc:
        logger.exception("hitting stats failed for player %s", player_id)
        stat_errors.append(f"Batting statistics unavailable ({exc}).")

    try:
        yby_p = fetch_json(
            f"/people/{player_id}/stats",
            params={"stats": "yearByYear", "group": "pitching"},
            app=app,
        )
        car_p = fetch_json(
            f"/people/{player_id}/stats",
            params={"stats": "careerRegularSeason", "group": "pitching"},
            app=app,
        )
        pr_p = fetch_json(
            f"/people/{player_id}/stats",
            params={
                "stats": "projected",
                "group": "pitching",
                "season": season_val,
            },
            app=app,
        )

        yby_splits_p = _filter_mlb_regular_splits((yby_p.get("stats") or [{}])[0].get("splits") or [])
        yby_splits_p.sort(key=_season_sort_key_asc)

        car_splits_p = (car_p.get("stats") or [{}])[0].get("splits") or []
        career_stat_p = (car_splits_p[0].get("stat") if car_splits_p else {}) or {}

        proj_splits_p = (pr_p.get("stats") or [{}])[0].get("splits") or []
        proj_stat_p = (proj_splits_p[0].get("stat") if proj_splits_p else None) or None

        want_pitching = (
            bool(yby_splits_p)
            or _has_meaningful_pitching(career_stat_p)
            or bool(proj_stat_p)
        )

        if want_pitching:
            team_ids_p: set[int] = set()
            for sp in yby_splits_p:
                tid = _split_team_id(sp.get("team"))
                if tid:
                    team_ids_p.add(tid)
            for sp in car_splits_p:
                tid = _split_team_id(sp.get("team"))
                if tid:
                    team_ids_p.add(tid)
            if current_tid:
                team_ids_p.add(current_tid)
            abbr_map_p = _fetch_team_abbr_map(app, team_ids_p)

            season_rows_p: list[dict[str, Any]] = []
            for sp in yby_splits_p:
                st = sp.get("stat") or {}
                tid = _split_team_id(sp.get("team"))
                abbr = abbr_map_p.get(tid, "—") if tid else "—"
                sk = str(sp.get("season") or "")
                season_rows_p.append(
                    _pitching_stat_row(
                        kind="season",
                        year_display=sk,
                        team_tid=tid,
                        team_abbr=abbr,
                        stat=st,
                        season_key=sk,
                    )
                )

            proj_row_p = None
            if proj_stat_p:
                ptid = current_tid
                pabbr = abbr_map_p.get(ptid, "—") if ptid else "—"
                proj_row_p = _pitching_stat_row(
                    kind="projection",
                    year_display="Proj",
                    team_tid=ptid,
                    team_abbr=pabbr,
                    stat=proj_stat_p,
                )

            body_rows_p = _merge_projection_after_season(season_rows_p, proj_row_p, season_val)

            if car_splits_p or _has_meaningful_pitching(career_stat_p):
                ctid = _split_team_id(car_splits_p[0].get("team")) if car_splits_p else None
                cabbr = abbr_map_p.get(ctid, "—") if ctid else "—"
                body_rows_p.append(
                    _pitching_stat_row(
                        kind="career",
                        year_display="Totals",
                        team_tid=ctid,
                        team_abbr=cabbr,
                        stat=career_stat_p,
                    )
                )

            pitching_block = {
                "title": "Pitching",
                "columns": PITCHING_CAREER_COLUMNS,
                "rows": body_rows_p,
            }
    except RuntimeError as exc:
        logger.exception("pitching stats failed for player %s", player_id)
        stat_errors.append(f"Pitching statistics unavailable ({exc}).")

    recent_games: list[dict[str, Any]] = []
    recent_games_error: str | None = None

    if pitching_block is not None and hitting_block is None:
        game_log_group = "pitching"
    elif hitting_block is not None and pitching_block is None:
        game_log_group = "hitting"
    elif pitching_block is not None and hitting_block is not None:
        game_log_group = "pitching" if _is_primary_pitcher(person) else "hitting"
    else:
        game_log_group = "pitching" if _is_primary_pitcher(person) else "hitting"

    today = dt.date.today()
    start_s = f"{season_val}-02-15"
    end_s = today.isoformat()
    hydrate_gl = _hydrate_game_log(game_log_group, season_val, start_s, end_s)

    try:
        gl_data = fetch_json(
            f"/people/{player_id}",
            params={"hydrate": hydrate_gl},
            app=app,
        )
        gl_people = gl_data.get("people") or []
        if gl_people:
            stats_blocks = gl_people[0].get("stats") or []
            splits_gl: list[dict[str, Any]] = []
            for block in stats_blocks:
                gname = str((block.get("group") or {}).get("displayName") or "").lower()
                if gname != game_log_group:
                    continue
                splits_gl = block.get("splits") or []
                break
            splits_gl = [sp for sp in splits_gl if str(sp.get("gameType") or "R") == "R"]
            splits_gl.sort(key=lambda sp: str(sp.get("date") or ""), reverse=True)
            opp_ids: set[int] = set()
            for sp in splits_gl[:25]:
                oid = _split_team_id(sp.get("opponent"))
                if oid:
                    opp_ids.add(oid)
            gl_abbr = _fetch_team_abbr_map(app, opp_ids)
            for sp in splits_gl[:7]:
                stat = sp.get("stat") or {}
                opp = sp.get("opponent")
                oid = _split_team_id(opp)
                recent_games.append(
                    {
                        "date": _fmt_game_date(sp.get("date")),
                        "opp": _opp_display(opp, gl_abbr),
                        "summary": _fmt_stat(stat.get("summary")),
                    }
                )
    except RuntimeError as exc:
        logger.exception("game log failed for player %s", player_id)
        recent_games_error = str(exc)

    return {
        "player_id": player_id,
        "page_title": hero["name_last_first"],
        "hero": hero,
        "season_val": season_val,
        "hitting_block": hitting_block,
        "pitching_block": pitching_block,
        "stat_errors": stat_errors,
        "recent_games": recent_games,
        "recent_games_error": recent_games_error,
        "recent_games_group": game_log_group,
    }
