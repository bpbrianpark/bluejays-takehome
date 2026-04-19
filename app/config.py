import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me")

    # MLB StatsAPI base (override when wiring real endpoints).
    STATSAPI_BASE = os.environ.get(
        "STATSAPI_BASE",
        "https://statsapi.mlb.com/api/v1",
    )

    # SQLite filename or path; relative paths resolve under the project/instance folder.
    DATABASE = os.environ.get("DATABASE_URL", "mlb.sqlite")

    # Optional HTTP response cache TTL in seconds (0 = caching disabled).
    HTTP_CACHE_TTL_SECONDS = int(os.environ.get("HTTP_CACHE_TTL_SECONDS", "300"))
