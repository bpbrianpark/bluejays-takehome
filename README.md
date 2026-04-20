# bluejays-takehome

Toronto Blue Jays Developer Project

## Stack

- **Flask 3**, **Jinja** templates
- **Bootstrap 5**, **Font Awesome 6**, **Inter** + **Chivo Mono** (see `app/static/css/app.css`)
- **httpx** for HTTP, optional **SQLite** HTTP cache (`instance/mlb.sqlite` by default)

## Requirements

- Python **3.10+** (3.11+ recommended)
- Network access to the MLB Stats API and RSS feeds (first load may be slower while the HTTP cache warms up)

## How to run the program

1. **Clone the repository** (or unzip it) and open a terminal in the project root (`bluejays-takehome/`).

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

   On Windows (PowerShell or Command Prompt):

   ```text
   .venv\Scripts\activate
   ```

3. **Install the app** (editable install from `pyproject.toml`):

   ```bash
   pip install -e .
   ```

4. **Optional — environment variables**  
   Copy or create a `.env` file in the project root if you want to override defaults (see **Configuration** below). The app loads `.env` automatically via `python-dotenv`.

5. **Start the development server**

   ```bash
   flask --app app:create_app run --debug
   ```

   Equivalent:

   ```bash
   python -m flask --app app:create_app run --debug
   ```

6. **Open the app in a browser**  
   Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) (Flask’s default port is **5000**).

To stop the server, press `Ctrl+C` in the terminal.

## Configuration

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` | Flask session signing (set in production) |
| `STATSAPI_BASE` | StatsAPI base URL (default: `https://statsapi.mlb.com/api/v1`) |
| `DATABASE_URL` | SQLite filename or path for the HTTP cache DB |
| `HTTP_CACHE_TTL_SECONDS` | Cache TTL; use `0` to disable |
| `MLB_NEWS_RSS_URL` | MLB.com RSS URL for landing news |
| `LANDING_LEADER_CATEGORIES` | Comma-separated StatsAPI `leaderCategories` for the landing page |
| `LEADERBOARD_HITTING_CATEGORIES` | Comma-separated hitting leader categories for `/leaders` |
| `LEADERBOARD_PITCHING_CATEGORIES` | Comma-separated pitching leader categories for `/leaders` |
| `LEADERBOARD_ROW_LIMIT` | Number of players shown per category on `/leaders` (default: `15`) |
