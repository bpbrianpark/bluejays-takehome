from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlencode

import httpx
from flask import Flask, current_app

from app.extensions import cache_get, cache_set

logger = logging.getLogger(__name__)


def fetch_json(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    app: Flask | None = None,
) -> dict[str, Any]:
    flask_app = app or current_app
    base = str(flask_app.config["STATSAPI_BASE"]).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    url = f"{base}{suffix}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    cached = cache_get(flask_app, url)
    if cached is not None:
        return json.loads(cached)

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            body = response.text
    except httpx.HTTPError as exc:
        logger.exception("StatsAPI request failed: %s", url)
        raise RuntimeError(f"StatsAPI request failed: {url}") from exc

    cache_set(flask_app, url, body)
    return json.loads(body)
