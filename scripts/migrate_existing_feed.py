"""Разовая миграция существующих записей news-data.js в data/state.json (bootstrap).

Рекорды импортируются с summarized=true (контент уже выверен конвейером),
first_seen = дата новости 12:00 UTC. Повторный запуск — идемпотентный по URL.
Запуск из customstech-landing: python scripts/migrate_existing_feed.py
"""

import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
js_text = (root / "news-data.js").read_text(encoding="utf-8")

# Файл — JS-литерал (ключи без кавычек): вычисляем массив через node.
import subprocess
js_expr = js_text[js_text.index("[") : js_text.rindex("]") + 1]
proc = subprocess.run(
    ["node", "-e", f"console.log(JSON.stringify({js_expr}))"],
    capture_output=True, text=True, encoding="utf-8", check=True)
items = json.loads(proc.stdout)


def url_key(url: str) -> str:
    return hashlib.sha1(url.rstrip("/").lower().encode()).hexdigest()


def title_key(title: str, date: str) -> str:
    raw = f"{title.strip().lower()}:{date}"
    return hashlib.sha1(raw.encode()).hexdigest()


state_path = root / "data" / "state.json"
data = {"records": {}, "source_health": {}}
if state_path.exists():
    data = json.loads(state_path.read_text(encoding="utf-8"))
records = data.setdefault("records", {})

added = 0
for item in items:
    url = item["url"]
    key = url_key(url)
    if key in records:  # идемпотентность
        continue
    date = item.get("date", "")
    records[key] = {
        "url": url,
        "title": item["title"],
        "title_key": title_key(item["title"], date),
        "date": date,
        "summary": item["summary"],
        "topic": item.get("topic", "НПА"),
        "source": item.get("source", ""),
        "first_seen": f"{date or '1970-01-01'}T12:00:00+00:00",
        "summarized": True,
        "image": item.get("image"),
        "video": item.get("video"),
    }
    added += 1

state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"migrated: {added}, total records: {len(records)}")