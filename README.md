# bluejays-takehome

Toronto Blue Jays Developer Project

## Stack

- **Flask 3**, **Jinja** templates
- **Bootstrap 5**, **Font Awesome 6**, **Inter** + **Chivo Mono** (see `app/static/css/app.css`)
- **httpx** for HTTP, optional **SQLite** HTTP cache (`instance/mlb.sqlite` by default)

## Requirements

- Python **3.10+** (3.11+ recommended)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## Run

```bash
flask --app app:create_app run --debug
```

Then open http://127.0.0.1:5000/

## Configuration

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session signing (set in production) |
| `STATSAPI_BASE` | StatsAPI base URL (default: `https://statsapi.mlb.com/api/v1`) |
| `DATABASE_URL` | SQLite filename or path for the HTTP cache DB |
| `HTTP_CACHE_TTL_SECONDS` | Cache TTL; use `0` to disable |
| `MLB_NEWS_RSS_URL` | MLB.com RSS URL for landing news |
| `LANDING_LEADER_CATEGORIES` | Comma-separated StatsAPI `leaderCategories` for the landing page |
