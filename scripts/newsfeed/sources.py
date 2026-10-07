"""Сбор новостей из RSS и HTML-источников (по sources.yaml).

Перенос из customsnews-law-monitor/src/sources.py с отвязкой от Config:
список источников передаётся явно.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
}


@dataclass
class NewsItem:
    title: str
    url: str
    published_at: datetime | None
    source_name: str
    summary: str = ""
    direction: str | None = None  # направление таможенного законодательства
    relevance: int = 0  # число совпадений с ключевыми словами направления
    requisites: str | None = None  # реквизиты правового акта (тип, дата, номер)

    def text_for_check(self) -> str:
        return f"{self.title} {self.summary}".lower()


def load_sources(path: str) -> dict:
    """Прочитать sources.yaml целиком (sources, keywords, markers, topic_map)."""
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_rss_date(entry) -> datetime | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    return None


def _fetch(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text


def _matches(text: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _clean_url(url: str, base: str) -> str:
    if url.startswith("http"):
        return url
    return urljoin(base, url)


def collect_rss(source: dict) -> list[NewsItem]:
    name = source["name"]
    url = source["url"]
    keywords = source.get("keywords", [])

    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        if not title or not link:
            continue

        text = f"{title} {summary}".lower()
        if not _matches(text, keywords):
            continue

        items.append(NewsItem(
            title=title,
            url=_clean_url(link, url),
            published_at=_parse_rss_date(entry),
            source_name=name,
            summary=summary,
        ))
    return items


def _parse_html_date(date_text: str) -> datetime | None:
    if not date_text:
        return None
    for pattern in (r"(\d{2})\.(\d{2})\.(\d{4})", r"(\d{4})-(\d{2})-(\d{2})"):
        match = re.search(pattern, date_text)
        if match:
            parts = match.groups()
            if len(parts[0]) == 4:
                return datetime(int(parts[0]), int(parts[1]), int(parts[2]), tzinfo=timezone.utc)
            return datetime(int(parts[2]), int(parts[1]), int(parts[0]), tzinfo=timezone.utc)
    return None


import re  # noqa: E402  (после dataclass, до использования в _parse_html_date)


def collect_html(source: dict) -> list[NewsItem]:
    name = source["name"]
    url = source["url"]
    keywords = source.get("keywords", [])
    list_selector = source.get("list_selector", "article")
    title_selector = source.get("title_selector", "h2 a, h3 a, a")
    link_selector = source.get("link_selector", "a")
    date_selector = source.get("date_selector", ".date, time")

    html = _fetch(url, timeout=30)
    soup = BeautifulSoup(html, "lxml")
    items = []
    for block in soup.select(list_selector):
        title_tag = block.select_one(title_selector)
        if not title_tag:
            continue
        title = title_tag.get_text(strip=True)
        link_tag = block.select_one(link_selector) or title_tag
        link = (link_tag.get("href") or "").strip()
        if not title or not link:
            continue

        date_tag = block.select_one(date_selector)
        date_text = date_tag.get_text(strip=True) if date_tag else ""
        published_at = _parse_html_date(date_text)

        summary = block.get_text(strip=True, separator=" ")[:500]
        text = f"{title} {summary}".lower()
        if not _matches(text, keywords):
            continue

        items.append(NewsItem(
            title=title,
            url=_clean_url(link, url),
            published_at=published_at,
            source_name=name,
            summary=summary,
        ))
    return items


def collect_all(cfg: dict) -> list[NewsItem]:
    """Собрать новости из всех источников cfg['sources'] с ретраем и логом."""
    items = []
    for source in cfg.get("sources", []):
        try:
            for attempt in (0, 1, 2):
                if attempt:
                    # бэкофф 5/15 с — щадяще к антифроду источников и стабильнее
                    import time
                    time.sleep(5 * attempt)
                try:
                    if source.get("type") == "rss":
                        batch = collect_rss(source)
                    elif source.get("type") == "html":
                        batch = collect_html(source)
                    else:
                        batch = None
                    break
                except Exception:
                    batch = None
            if batch is None:
                batch = []
            items.extend(batch)
            print(f"[sources] {source['name']}: {len(batch)} items")
        except Exception as exc:
            print(f"[sources] {source['name']}: failed: {exc}")
    return items