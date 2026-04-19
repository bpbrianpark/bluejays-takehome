"""SQLite helpers and optional HTTP cache."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask


def init_extensions(app: Flask) -> None:
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db_path = _resolve_db_path(app)
    app.extensions["sqlite_path"] = db_path
    _ensure_schema(db_path)


def _resolve_db_path(app: Flask) -> Path:
    raw = app.config["DATABASE"]
    path = Path(raw)
    if path.is_absolute():
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    project_root = Path(app.root_path).parent
    if len(path.parts) == 1:
        path = Path(app.instance_path) / path.name
    else:
        path = project_root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _ensure_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS http_cache (
                cache_key TEXT PRIMARY KEY,
                body TEXT NOT NULL,
                fetched_at REAL NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def get_sqlite_path(app: Flask) -> Path:
    return app.extensions["sqlite_path"]


def cache_get(app: Flask, key: str) -> str | None:
    ttl = app.config.get("HTTP_CACHE_TTL_SECONDS", 0)
    if ttl <= 0:
        return None
    db_path = get_sqlite_path(app)
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT body, fetched_at FROM http_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        body, fetched_at = row
        if time.time() - fetched_at > ttl:
            conn.execute("DELETE FROM http_cache WHERE cache_key = ?", (key,))
            conn.commit()
            return None
        return body
    finally:
        conn.close()


def cache_set(app: Flask, key: str, body: str) -> None:
    ttl = app.config.get("HTTP_CACHE_TTL_SECONDS", 0)
    if ttl <= 0:
        return
    db_path = get_sqlite_path(app)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO http_cache (cache_key, body, fetched_at)
            VALUES (?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                body = excluded.body,
                fetched_at = excluded.fetched_at
            """,
            (key, body, time.time()),
        )
        conn.commit()
    finally:
        conn.close()
