from __future__ import annotations

import logging
from typing import Any

from flask import Flask

from app.services.landing_data import team_logo_url
from app.services.mlb_stats import fetch_json

logger = logging.getLogger(__name__)


def register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_nav_teams() -> dict[str, Any]:
        try:
            data = fetch_json("/teams", params={"sportId": 1}, app=app)
            teams: list[dict[str, Any]] = []
            for t in data.get("teams", []) or []:
                if t.get("id") is None:
                    continue
                tid = int(t["id"])
                abbr = str(t.get("abbreviation") or t.get("teamCode") or "").strip().upper()
                teams.append(
                    {
                        "id": tid,
                        "name": str(t.get("name") or ""),
                        "abbr": abbr or str(t.get("name") or "")[:3].upper(),
                        "logo_url": team_logo_url(tid),
                    }
                )
            teams.sort(key=lambda x: x["abbr"])
            return {"nav_teams": teams}
        except Exception:
            logger.debug("Nav teams load skipped", exc_info=True)
            return {"nav_teams": []}
