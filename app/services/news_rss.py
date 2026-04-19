from __future__ import annotations

import logging
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from xml.etree import ElementTree

import httpx
from flask import Flask

from app.extensions import cache_get, cache_set

logger = logging.getLogger(__name__)

_DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


def _fetch_text(app: Flask, url: str) -> str:
    cached = cache_get(app, url)
    if cached is not None:
        return cached
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            body = response.text
    except httpx.HTTPError as exc:
        logger.exception("RSS request failed: %s", url)
        raise RuntimeError(f"RSS request failed: {url}") from exc
    cache_set(app, url, body)
    return body


def _local_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _item_image_href(item: ElementTree.Element) -> str:
    for el in item:
        if _local_tag(el.tag) == "image":
            href = el.get("href") or ""
            if href:
                return href
    return ""


def _format_pub_date(pub: str) -> tuple[str, str]:
    if not pub.strip():
        return "", ""
    try:
        parsed = parsedate_to_datetime(pub)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local = parsed.astimezone()
        date_s = f"{local.strftime('%b')} {local.day}, {local.year}"
        clock = local.strftime("%I:%M %p")
        time_s = clock[1:] if clock.startswith("0") else clock
        return date_s, time_s
    except (TypeError, ValueError, OverflowError):
        return pub, ""


def fetch_news_items(app: Flask, rss_url: str | None = None, *, limit: int = 12) -> list[dict[str, Any]]:
    url = rss_url or app.config["MLB_NEWS_RSS_URL"]
    xml_text = _fetch_text(app, url)

    root = ElementTree.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict[str, Any]] = []
    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        pub_el = item.find("pubDate")

        title = _element_text(title_el).strip()
        link = _element_text(link_el).strip()
        published_raw = _element_text(pub_el).strip()

        creator_el = item.find("dc:creator", _DC_NS)
        author = _element_text(creator_el).strip()

        image_url = _item_image_href(item)
        date_display, time_display = _format_pub_date(published_raw)

        if not title:
            continue
        items.append(
            {
                "title": title,
                "link": link or "#",
                "published": published_raw,
                "author": author,
                "image_url": image_url,
                "date_display": date_display,
                "time_display": time_display,
            }
        )
        if len(items) >= limit:
            break

    return items


def _element_text(el: ElementTree.Element | None) -> str:
    if el is None:
        return ""
    return "".join(el.itertext()).strip()
