"""Классификация новостей по правилам (перенос из customsnews-law-monitor/src/collector.py).

Без зависимостей от Config/State: маркеры передаются из sources.yaml.
"""

import re

from .sources import NewsItem

# Реквизиты правового акта: тип акта + дата + номер (приказ ФТС от 26.08.2026 № 641, 218-ФЗ и т.п.)
_REQUISITE_PATTERNS = [
    r"(?:[Фф]едеральный\s+закон|[Пп]риказ|[Пп]остановлени[ея]|[Пп]исьмо|[Рр]ешени[ея]|[Рр]аспоряжени[ея]|[Уу]каз|"
    r"[Ии]нструкци[яи])\s+(?:[ФФТС][А-Яа-яё]+\s+)?от\s+\d{1,2}\.\d{1,2}\.\d{2,4}\s*(?:г\.?|года)?\s*№\s*[\d/]+(?:[-–—]?\w+)?",
    r"№\s*\d+[-–—]?\w*ФЗ",
    r"от\s+\d{1,2}\.\d{1,2}\.\d{2,4}\s*(?:г\.?|года)?\s*№\s*[\d/]+(?:[-–—]?\w+)?",
]
_REQUISITE_RE = [re.compile(p) for p in _REQUISITE_PATTERNS]


def extract_requisites(text: str) -> str | None:
    """Вытащить реквизиты правового акта (тип/орган, дата, номер) из текста новости."""
    found: list[str] = []
    for regex in _REQUISITE_RE:
        for m in regex.finditer(text):
            fragment = re.sub(r"\s+", " ", m.group(0)).strip(" .,;:«»")
            if fragment and fragment not in found:
                found.append(fragment)
        if found:
            break
    return "; ".join(found[:3]) or None


def is_excluded(item: NewsItem, exclude: list[str]) -> bool:
    text = item.text_for_check()
    return any(kw.lower() in text for kw in exclude)


def has_common_keyword(item: NewsItem, common: list[str]) -> bool:
    text = item.text_for_check()
    return any(kw.lower() in text for kw in common)


def is_act(item: NewsItem, markers: list[str]) -> bool:
    """Новость должна быть о нормативном акте (закон, приказ, правила и т.п.)."""
    text = item.text_for_check()
    return any(marker.lower() in text for marker in markers)


def is_individual_only(item: NewsItem, markers: list[str]) -> bool:
    """Акт только для физических лиц — по заголовку."""
    title = item.title.lower()
    return any(marker.lower() in title for marker in markers)


def match_direction(item: NewsItem, directions: list[dict]) -> tuple[str | None, int]:
    """Направление с максимальным числом вхождений ключевых слов и этот максимум."""
    text = item.text_for_check()
    best_name, best_score = None, 0
    for direction in directions:
        score = sum(text.count(kw.lower()) for kw in direction["keywords"])
        if score > best_score:
            best_name, best_score = direction["name"], score
    return best_name, best_score


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Убрать повторы внутри одного сбора (по URL — точно, по (title, date) — подстраховка)."""
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result = []
    for item in items:
        url_key = item.url.rstrip("/").lower()
        title_key = re.sub(r"\s+", " ", item.title.strip().lower())
        title_key = title_key + ":" + (item.published_at.strftime("%Y-%m-%d") if item.published_at else "")
        if url_key in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(url_key)
        seen_titles.add(title_key)
        result.append(item)
    return result


def rank_and_cap(items: list[NewsItem], max_per_day: int = 5) -> list[NewsItem]:
    """Сортировка по дате desc + релевантности, не более max_per_day на день."""
    items.sort(
        key=lambda x: (x.published_at, x.relevance),
        reverse=True,
    )
    result, counts = [], {}
    for item in items:
        day = item.published_at.strftime("%Y-%m-%d") if item.published_at else "nodate"
        if counts.get(day, 0) >= max_per_day:
            continue
        counts[day] = counts.get(day, 0) + 1
        result.append(item)
    return result