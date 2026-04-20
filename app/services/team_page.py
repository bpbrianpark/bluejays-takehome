from __future__ import annotations

import logging
import re
from typing import Any

from flask import Flask

from app.services.landing_data import player_headshot_url
from app.services.mlb_stats import fetch_json

logger = logging.getLogger(__name__)

BATTING_STAT_COLUMNS: list[dict[str, str]] = [
    {"key": "age", "label": "Age"},
    {"key": "b", "label": "B"},
    {"key": "t", "label": "T"},
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
]

PITCHING_STAT_COLUMNS: list[dict[str, str]] = [
    {"key": "age", "label": "Age"},
    {"key": "b", "label": "B"},
    {"key": "t", "label": "T"},
    {"key": "w", "label": "W"},
    {"key": "l", "label": "L"},
    {"key": "era", "label": "ERA"},
    {"key": "g", "label": "G"},
    {"key": "gs", "label": "GS"},
    {"key": "sv", "label": "SV"},
    {"key": "ip", "label": "IP"},
    {"key": "h", "label": "H"},
    {"key": "r", "label": "R"},
    {"key": "er", "label": "ER"},
    {"key": "hr", "label": "HR"},
    {"key": "bb", "label": "BB"},
    {"key": "so", "label": "SO"},
    {"key": "whip", "label": "WHIP"},
    {"key": "avg", "label": "AVG"},
]

_MLB_COM_TEAM_SLUG_OVERRIDES: dict[int, str] = {
    109: "dbacks",
}

_CHUNK_SIZE = 35


def _slug_from_club_name(club_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", club_name.strip().lower())


def mlb_com_team_news_rss_url(team: dict[str, Any]) -> str:
    tid = team.get("id")
    if tid is not None and int(tid) in _MLB_COM_TEAM_SLUG_OVERRIDES:
        slug = _MLB_COM_TEAM_SLUG_OVERRIDES[int(tid)]
    else:
        slug = _slug_from_club_name(str(team.get("clubName") or team.get("name") or ""))
    return f"https://www.mlb.com/{slug}/feeds/news/rss.xml"


def load_team_record(team_id: int, *, app: Flask) -> dict[str, Any] | None:
    try:
        data = fetch_json(f"/teams/{team_id}", app=app)
    except RuntimeError:
        logger.debug("Team %s not found or StatsAPI error", team_id, exc_info=True)
        return None
    teams = data.get("teams") or []
    if not teams:
        return None
    return teams[0]


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_gb(raw: Any) -> str:
    if raw is None:
        return "—"
    s = str(raw).strip()
    if s in {"", "-", "—"}:
        return "—"
    try:
        x = float(s)
        if x == 0:
            return "—"
    except (TypeError, ValueError):
        pass
    return s


def load_standings_snippet(app: Flask, team_id: int) -> dict[str, Any] | None:
    data = fetch_json(
        "/standings",
        params={"leagueId": "103,104", "hydrate": "team,division,league"},
        app=app,
    )
    for rec in data.get("records") or []:
        div_info = rec.get("division") or {}
        div_short = str(div_info.get("nameShort") or div_info.get("name") or "").strip()
        for tr in rec.get("teamRecords") or []:
            team = tr.get("team") or {}
            tid = team.get("id")
            if tid is None or int(tid) != int(team_id):
                continue
            wins = int(tr.get("wins") or 0)
            losses = int(tr.get("losses") or 0)
            pct = str(tr.get("winningPercentage") or "").strip()
            rank_raw = tr.get("divisionRank")
            try:
                rank_n = int(rank_raw) if rank_raw is not None else None
            except (TypeError, ValueError):
                rank_n = None
            rank_ord = _ordinal(rank_n) if rank_n is not None else "—"
            rank_in_division = ""
            if rank_n is not None and div_short:
                rank_in_division = f"{rank_ord} in {div_short}"
            elif div_short and rank_n is None:
                rank_in_division = div_short
            return {
                "division_short": div_short,
                "division_rank": rank_n,
                "division_rank_ord": rank_ord,
                "rank_in_division": rank_in_division,
                "w": wins,
                "l": losses,
                "pct": pct,
                "games_back_raw": tr.get("gamesBack"),
                "games_back_display": _format_gb(tr.get("gamesBack")),
            }
    return None


def is_pitcher_entry(entry: dict[str, Any]) -> bool:
    person = entry.get("person") or {}
    pos = person.get("primaryPosition") or entry.get("position") or {}
    return str(pos.get("code") or "") == "1"


def _jersey_sort_key(entry: dict[str, Any]) -> tuple[int, str]:
    raw = str(entry.get("jerseyNumber") or "").strip()
    try:
        return (int(raw), raw)
    except ValueError:
        return (9999, raw)


def _bat_side_code(person: dict[str, Any]) -> str:
    side = person.get("batSide") or {}
    return str(side.get("code") or "—")


def _throw_side_code(person: dict[str, Any]) -> str:
    hand = person.get("pitchHand") or person.get("throwSide") or {}
    return str(hand.get("code") or "—")


def _pos_abbr(entry: dict[str, Any]) -> str:
    pos = entry.get("position") or (entry.get("person") or {}).get("primaryPosition") or {}
    return str(pos.get("abbreviation") or "—")


def _hydrate_stats(group: str, season: int) -> str:
    return f"stats(group=[{group}],type=[season],season={season})"


def fetch_people_stats_map(
    app: Flask,
    person_ids: list[int],
    *,
    season: int,
    group: str,
) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    if not person_ids:
        return out
    hydrate = _hydrate_stats(group, season)
    for i in range(0, len(person_ids), _CHUNK_SIZE):
        chunk = person_ids[i : i + _CHUNK_SIZE]
        ids_param = ",".join(str(x) for x in chunk)
        data = fetch_json(
            "/people",
            params={"personIds": ids_param, "hydrate": hydrate},
            app=app,
        )
        for person in data.get("people") or []:
            pid = person.get("id")
            if pid is None:
                continue
            pid_i = int(pid)
            stats_blocks = person.get("stats") or []
            stat_dict: dict[str, Any] | None = None
            for block in stats_blocks:
                g = (block.get("group") or {}).get("displayName") or ""
                if str(g).lower() != group.lower():
                    continue
                splits = block.get("splits") or []
                if splits:
                    stat_dict = (splits[0].get("stat")) or {}
                    break
            out[pid_i] = stat_dict or {}
    return out


def _fmt_stat(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        if isinstance(val, float) and val.is_integer():
            return str(int(val))
        return str(val)
    s = str(val).strip()
    return s if s else "—"


def player_last_first(person: dict[str, Any]) -> str:
    lf = str(person.get("lastFirstName") or "").strip()
    if lf:
        return lf
    last = str(person.get("lastName") or "").strip()
    first = str(person.get("firstName") or "").strip()
    if last and first:
        return f"{last}, {first}"
    return str(person.get("fullName") or "").strip()


_TEAM_LEADER_LABELS: dict[str, str] = {
    "homeRuns": "Home Runs",
    "onBasePlusSlugging": "OPS",
    "strikeouts": "Strikeouts",
    "earnedRunAverage": "ERA",
}
_TEAM_LEADER_FIELD: dict[str, tuple[str, str, str]] = {
    "homeRuns": ("hitting", "homeRuns", "max"),
    "onBasePlusSlugging": ("hitting", "ops", "max"),
    "strikeouts": ("pitching", "strikeOuts", "max"),
    "earnedRunAverage": ("pitching", "era", "min"),
}


def _numeric_for_compare(stats: dict[str, Any], api_key: str) -> float | None:
    v = stats.get(api_key)
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        if s.startswith("."):
            return float(f"0{s}")
        return float(s)
    except (TypeError, ValueError):
        return None


def _hitting_leader_pool(
    roster: list[dict[str, Any]],
    hitting_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in roster:
        person = entry.get("person") or {}
        pid = person.get("id")
        if pid is None:
            continue
        pid_i = int(pid)
        pitcher = is_pitcher_entry(entry)
        stats = hitting_map.get(pid_i) or {}
        pa = stats.get("plateAppearances")
        try:
            pa_i = int(pa) if pa is not None else 0
        except (TypeError, ValueError):
            pa_i = 0
        if pitcher and pa_i <= 0:
            continue
        j = str(entry.get("jerseyNumber") or person.get("primaryNumber") or "").strip()
        try:
            ji = int(j)
        except ValueError:
            ji = 9999
        out.append(
            {
                "player_id": pid_i,
                "person": person,
                "stats": stats,
                "sort_key": (ji, player_last_first(person).lower()),
            }
        )
    return out


def _pitching_leader_pool(
    roster: list[dict[str, Any]],
    pitching_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entry in roster:
        if not is_pitcher_entry(entry):
            continue
        person = entry.get("person") or {}
        pid = person.get("id")
        if pid is None:
            continue
        pid_i = int(pid)
        stats = pitching_map.get(pid_i) or {}
        j = str(entry.get("jerseyNumber") or person.get("primaryNumber") or "").strip()
        try:
            ji = int(j)
        except ValueError:
            ji = 9999
        out.append(
            {
                "player_id": pid_i,
                "person": person,
                "stats": stats,
                "sort_key": (ji, player_last_first(person).lower()),
            }
        )
    return out


def _pick_stat_leader(
    pool: list[dict[str, Any]],
    api_key: str,
    mode: str,
) -> dict[str, Any] | None:
    candidates: list[tuple[float, dict[str, Any]]] = []
    for p in pool:
        nu = _numeric_for_compare(p["stats"], api_key)
        if nu is None:
            continue
        candidates.append((nu, p))
    if not candidates:
        return None
    if mode == "max":
        candidates.sort(key=lambda t: (-t[0], t[1]["sort_key"]))
    else:
        candidates.sort(key=lambda t: (t[0], t[1]["sort_key"]))
    return candidates[0][1]


def build_team_leader_blocks(
    roster: list[dict[str, Any]],
    hitting_map: dict[int, dict[str, Any]],
    pitching_map: dict[int, dict[str, Any]],
    *,
    team_abbr: str,
    categories: tuple[str, ...],
) -> list[dict[str, Any]]:
    hit_pool = _hitting_leader_pool(roster, hitting_map)
    pit_pool = _pitching_leader_pool(roster, pitching_map)
    blocks: list[dict[str, Any]] = []
    for cat in categories:
        spec = _TEAM_LEADER_FIELD.get(cat)
        if spec is None:
            continue
        group, api_key, mode = spec
        pool = hit_pool if group == "hitting" else pit_pool
        winner = _pick_stat_leader(pool, api_key, mode)
        label = _TEAM_LEADER_LABELS.get(cat, cat.replace("_", " ").title())
        if winner is None:
            blocks.append(
                {
                    "category": cat,
                    "label": label,
                    "rows": [],
                    "error": None,
                }
            )
            continue
        pid = int(winner["player_id"])
        blocks.append(
            {
                "category": cat,
                "label": label,
                "rows": [
                    {
                        "player_id": pid,
                        "player": player_last_first(winner["person"]),
                        "headshot_url": player_headshot_url(pid),
                        "value": _fmt_stat(winner["stats"].get(api_key)),
                        "team_abbr": team_abbr or "—",
                    }
                ],
                "error": None,
            }
        )
    return blocks


def build_batting_rows(
    roster: list[dict[str, Any]],
    hitting_map: dict[int, dict[str, Any]],
    *,
    season_age_fallback: dict[int, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in roster:
        person = entry.get("person") or {}
        pid = person.get("id")
        if pid is None:
            continue
        pid_i = int(pid)
        pitcher = is_pitcher_entry(entry)
        stats = hitting_map.get(pid_i) or {}
        pa = stats.get("plateAppearances")
        try:
            pa_i = int(pa) if pa is not None else 0
        except (TypeError, ValueError):
            pa_i = 0
        if pitcher and pa_i <= 0:
            continue

        age = stats.get("age") or person.get("currentAge") or season_age_fallback.get(pid_i)
        row = {
            "player_id": pid_i,
            "player_name": player_last_first(person),
            "headshot_url": player_headshot_url(pid_i, width=72),
            "pos": _pos_abbr(entry),
            "jersey": str(entry.get("jerseyNumber") or person.get("primaryNumber") or "").strip() or "—",
            "age": _fmt_stat(age),
            "b": _bat_side_code(person),
            "t": _throw_side_code(person),
            "g": _fmt_stat(stats.get("gamesPlayed")),
            "pa": _fmt_stat(stats.get("plateAppearances")),
            "ab": _fmt_stat(stats.get("atBats")),
            "r": _fmt_stat(stats.get("runs")),
            "h": _fmt_stat(stats.get("hits")),
            "doubles": _fmt_stat(stats.get("doubles")),
            "triples": _fmt_stat(stats.get("triples")),
            "hr": _fmt_stat(stats.get("homeRuns")),
            "rbi": _fmt_stat(stats.get("rbi")),
            "bb": _fmt_stat(stats.get("baseOnBalls")),
            "so": _fmt_stat(stats.get("strikeOuts")),
            "sb": _fmt_stat(stats.get("stolenBases")),
            "cs": _fmt_stat(stats.get("caughtStealing")),
            "avg": _fmt_stat(stats.get("avg")),
            "obp": _fmt_stat(stats.get("obp")),
            "slg": _fmt_stat(stats.get("slg")),
            "ops": _fmt_stat(stats.get("ops")),
        }
        rows.append(row)
    rows.sort(key=lambda r: (_jersey_int(r["jersey"]), r["player_name"]))
    return rows


def _jersey_int(j: str) -> int:
    try:
        return int(str(j).strip())
    except ValueError:
        return 9999


def build_pitching_rows(
    roster: list[dict[str, Any]],
    pitching_map: dict[int, dict[str, Any]],
    *,
    season_age_fallback: dict[int, int],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in roster:
        if not is_pitcher_entry(entry):
            continue
        person = entry.get("person") or {}
        pid = person.get("id")
        if pid is None:
            continue
        pid_i = int(pid)
        stats = pitching_map.get(pid_i) or {}
        age = stats.get("age") or person.get("currentAge") or season_age_fallback.get(pid_i)
        row = {
            "player_id": pid_i,
            "player_name": player_last_first(person),
            "headshot_url": player_headshot_url(pid_i, width=72),
            "pos": _pos_abbr(entry),
            "jersey": str(entry.get("jerseyNumber") or person.get("primaryNumber") or "").strip() or "—",
            "age": _fmt_stat(age),
            "b": _bat_side_code(person),
            "t": _throw_side_code(person),
            "w": _fmt_stat(stats.get("wins")),
            "l": _fmt_stat(stats.get("losses")),
            "era": _fmt_stat(stats.get("era")),
            "g": _fmt_stat(stats.get("gamesPlayed")),
            "gs": _fmt_stat(stats.get("gamesStarted")),
            "sv": _fmt_stat(stats.get("saves")),
            "ip": _fmt_stat(stats.get("inningsPitched")),
            "h": _fmt_stat(stats.get("hits")),
            "r": _fmt_stat(stats.get("runs")),
            "er": _fmt_stat(stats.get("earnedRuns")),
            "hr": _fmt_stat(stats.get("homeRuns")),
            "bb": _fmt_stat(stats.get("baseOnBalls")),
            "so": _fmt_stat(stats.get("strikeOuts")),
            "whip": _fmt_stat(stats.get("whip")),
            "avg": _fmt_stat(stats.get("avg")),
            "ibb": _fmt_stat(stats.get("intentionalWalks")),
            "hld": _fmt_stat(stats.get("holds")),
        }
        rows.append(row)
    rows.sort(key=lambda r: (_jersey_int(r["jersey"]), r["player_name"]))
    return rows


def roster_age_fallback(roster: list[dict[str, Any]]) -> dict[int, int]:
    age_fb: dict[int, int] = {}
    for entry in roster:
        p = entry.get("person") or {}
        pid = p.get("id")
        if pid is None:
            continue
        ca = p.get("currentAge")
        if ca is not None:
            try:
                age_fb[int(pid)] = int(ca)
            except (TypeError, ValueError):
                pass
    return age_fb


def load_team_roster_entries(app: Flask, team_id: int, *, season: int) -> list[dict[str, Any]]:
    data = fetch_json(
        f"/teams/{team_id}/roster",
        params={
            "season": season,
            "rosterType": "active",
            "hydrate": (
                "person(batSide,pitchHand,primaryPosition,currentAge,primaryNumber,"
                "firstName,lastName,lastFirstName)"
            ),
        },
        app=app,
    )
    return list(data.get("roster") or [])
