import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")

    STATSAPI_BASE = os.environ.get(
        "STATSAPI_BASE",
        "https://statsapi.mlb.com/api/v1",
    )

    DATABASE = os.environ.get("DATABASE_URL", "mlb.sqlite")

    HTTP_CACHE_TTL_SECONDS = int(os.environ.get("HTTP_CACHE_TTL_SECONDS", "300"))

    MLB_NEWS_RSS_URL = os.environ.get(
        "MLB_NEWS_RSS_URL",
        "https://www.mlb.com/feeds/news/rss.xml",
    )

    _landing_cats_default = "homeRuns,onBasePlusSlugging,strikeouts,earnedRunAverage"
    LANDING_LEADER_CATEGORIES = tuple(
        c.strip()
        for c in os.environ.get(
            "LANDING_LEADER_CATEGORIES",
            _landing_cats_default,
        ).split(",")
        if c.strip()
    )

    _board_hit_default = "homeRuns,runs,rbi,onBasePlusSlugging"
    LEADERBOARD_HITTING_CATEGORIES = tuple(
        c.strip()
        for c in os.environ.get(
            "LEADERBOARD_HITTING_CATEGORIES",
            _board_hit_default,
        ).split(",")
        if c.strip()
    )

    _board_pit_default = "strikeouts,earnedRunAverage,wins,saves"
    LEADERBOARD_PITCHING_CATEGORIES = tuple(
        c.strip()
        for c in os.environ.get(
            "LEADERBOARD_PITCHING_CATEGORIES",
            _board_pit_default,
        ).split(",")
        if c.strip()
    )

    LEADERBOARD_ROW_LIMIT = int(os.environ.get("LEADERBOARD_ROW_LIMIT", "15"))
