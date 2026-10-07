"""Дедуп-хранилище между прогонами: data/state.json.

Рекорды хранятся по ключу sha1(url) (+ вторичный ключ sha1(title+date)),
поэтому LLM-пересказ вызывается только для новых URL.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone


def _url_key(url: str) -> str:
    return hashlib.sha1(url.rstrip("/").lower().encode()).hexdigest()


def _title_key(title: str, date: str) -> str:
    raw = f"{title.strip().lower()}:{date}"
    return hashlib.sha1(raw.encode()).hexdigest()


class State:
    def __init__(self, data: dict):
        self.records: dict[str, dict] = data.get("records", {})
        self.source_health: dict[str, dict] = data.get("source_health", {})

    @classmethod
    def load(cls, path=None):
        if path and path.exists():
            try:
                return cls(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return cls({})

    def to_dict(self) -> dict:
        return {"records": self.records, "source_health": self.source_health}

    def known(self, url: str, title: str = "", date: str = "") -> bool:
        if _url_key(url) in self.records:
            return True
        if title and date:
            return _title_key(title, date) in {r.get("title_key") for r in self.records.values()}
        return False

    def add(self, url: str, title: str, date: str, summary: str, topic: str,
            source: str, summarized: bool = True, image=None, video=None) -> None:
        self.records[_url_key(url)] = {
            "url": url,
            "title": title,
            "title_key": _title_key(title, date),
            "date": date,
            "summary": summary,
            "topic": topic,
            "source": source,
            "first_seen": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summarized": summarized,
            "image": image,
            "video": video,
        }

    def prune(self, days: int = 180) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        self.records = {k: v for k, v in self.records.items() if v.get("first_seen", "") > cutoff}

    def note_source(self, name: str, ok: bool, skip_after_fail: int, skip_runs: int) -> bool:
        """Обновить здоровье источника; вернуть True, если источник в скип-режиме"""
        entry = self.source_health.setdefault(name, {"last_ok": "", "consecutive_fail": 0})
        entry["consecutive_fail"] = 0 if ok else entry.get("consecutive_fail", 0) + 1
        if ok:
            entry["last_ok"] = datetime.now().strftime("%Y-%m-%d")
            return False
        return entry["consecutive_fail"] >= skip_after_fail and entry["consecutive_fail"] < skip_after_fail + skip_runs