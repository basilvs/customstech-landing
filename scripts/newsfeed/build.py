"""CLI сборки фида: источники -> правила -> новые -> LLM-пересказ -> state -> news.json/js.

Запуск из каталога scripts/ (чтобы import newsfeed работал):
  python -m newsfeed.build --sources sources.yaml --state ../data/state.json \
      --out ../news.json --js ../news-data.js --limit 30 --window-days 90 --max-new 10

Ключи: --no-llm (fallback-пересказ), --dry-run (не писать файлы).
Exit-код 0 всегда (кроме фатальных ошибок); change detection печатается в stdout.
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .classifier import (
    deduplicate,
    extract_requisites,
    has_common_keyword,
    is_act,
    is_excluded,
    is_individual_only,
    match_direction,
    rank_and_cap,
)
from .sources import collect_all, load_sources
from .state import State
from .summarizer import make_client, default_model, summarize
from .topics import resolve_topic


def sha256_of(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within_window(published_at, days: int) -> bool:
    if published_at is None:
        return True  # без даты не выбрасываем — но и в топ они не поднимутся
    return published_at >= datetime.now(timezone.utc) - timedelta(days=days)


def build(args) -> int:
    cfg = load_sources(args.sources)
    state = State.load(args.state)

    # --- 1. сбор ---
    items = deduplicate(collect_all(cfg))
    filtered = []
    for item in items:
        if is_excluded(item, cfg.get("exclude_keywords", [])):
            continue
        if not has_common_keyword(item, cfg.get("common_keywords", [])):
            continue
        if not is_act(item, cfg.get("act_markers", [])):
            continue
        if is_individual_only(item, cfg.get("individual_markers", [])):
            continue
        direction, relevance = match_direction(item, cfg.get("directions", []))
        item.direction = direction
        item.relevance = relevance
        item.requisites = extract_requisites(f"{item.title} {item.summary}")
        filtered.append(item)
    print(f"[build] после фильтра: {len(filtered)} items")

    # --- 2. новые (нет в state) в окне ---
    window_days = args.window_days
    fresh = [it for it in filtered
             if not state.known(it.url, it.title,
                                it.published_at.strftime("%Y-%m-%d") if it.published_at else "")
             and within_window(it.published_at, window_days)]
    fresh = rank_and_cap(fresh, max_per_day=args.max_per_day)[: args.max_new]
    print(f"[build] новых для пересказа: {len(fresh)}")

    # --- 3. пересказ новых ---
    client = None if args.no_llm else make_client()
    model = default_model()
    for item in fresh:
        result = summarize(client, model, item, timeout=args.llm_timeout)
        topic = resolve_topic(item.direction, True, result["topic"],
                              f"{item.title} {item.summary}")
        state.add(
            url=item.url,
            title=item.title,
            date=item.published_at.strftime("%Y-%m-%d") if item.published_at else "",
            summary=result["summary"],
            topic=topic,
            source=item.source_name,
            summarized=result["summarized"],
        )

    # --- 3b. до-пересказ старых записей с fallback-резюме ---
    if client is not None:
        stale = [r for r in state.records.values()
                 if not r.get("summarized", True)
                 and r.get("first_seen", "") < (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()]
        for record in stale:
            stub = type("Item", (), {
                "title": record["title"], "source_name": record["source"],
                "published_at": None,
                "summary": f"{record['title']} ({record['source']}, {record['date']})",
            })()
            result = summarize(client, model, stub, timeout=args.llm_timeout)
            if result["summarized"]:
                record["summary"] = result["summary"]
                record["summarized"] = True
        if stale:
            print(f"[build] до-пересказано старых: {len(stale)}")

    # --- 4. фид из state ---
    state.prune(days=180)
    items_out = sorted(
        state.records.values(),
        key=lambda r: (r["date"], r.get("first_seen", "")),
        reverse=True,
    )[: args.limit]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    feed = {"generated_at": now, "items": [
        {"date": r["date"], "topic": r["topic"], "title": r["title"],
         "summary": r["summary"], "source": r["source"], "url": r["url"],
         "image": r.get("image"), "video": r.get("video")}
        for r in items_out
    ]}
    js = "window.NEWS_FEED = " + json.dumps(feed["items"], ensure_ascii=False, indent=2) + ";\n"

    # --- 5. запись + change detection ---
    old_hash = sha256_of(args.out)
    new_hash = hashlib.sha256(
        json.dumps(feed, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    changed = old_hash != new_hash

    if not args.dry_run:
        args.out.write_text(
            json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.js.write_text(js, encoding="utf-8")
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(
            json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
    print(f"[build] в фиде: {len(items_out)} записей")
    print(f"changed={str(changed).lower()}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Сборка news.json/news-data.js")
    p.add_argument("--sources", type=Path, required=True)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--js", type=Path, required=True)
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--window-days", type=int, default=90)
    p.add_argument("--max-new", type=int, default=10)
    p.add_argument("--max-per-day", type=int, default=5)
    p.add_argument("--llm-timeout", type=int, default=30)
    p.add_argument("--no-llm", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return build(p.parse_args())


if __name__ == "__main__":
    sys.exit(main())