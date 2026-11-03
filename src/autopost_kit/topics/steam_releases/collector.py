"""Collect the games Steam lists for a given release day.

Strategy (kept cheap on purpose, since a single day can have 200+ games):

1. Walk the "coming soon" search sorted by release date, oldest first, and keep
   rows dated exactly ``target``. Stop at the first row dated after it.
   Vague dates ("Coming soon") can appear anywhere and are skipped.
2. Drop games carrying excluded content descriptors (adult content).
3. Rank by position in Steam's "popular upcoming" list.
4. Only the games that make it into a post get full details (``enrich``),
   one request each.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable

from autopost_kit.core.models import Item
from autopost_kit.topics.steam_releases.parsing import SearchRow, parse_release_date
from autopost_kit.topics.steam_releases.steam_store import GAMES_CATEGORY, SteamStore

log = logging.getLogger(__name__)

PAGE_SIZE = 100


def find_releases(
    store: SteamStore, target: date, max_pages: int = 40, only_games: bool = True
) -> list[SearchRow]:
    found: list[SearchRow] = []
    seen: set[str] = set()
    start = 0
    category = GAMES_CATEGORY if only_games else None
    for _ in range(max_pages):
        rows, total = store.search(
            "comingsoon", start=start, count=PAGE_SIZE, sort_by="Released_ASC", category=category
        )
        if not rows:
            return found
        for row in rows:
            released = row.release_date
            if released is None:
                continue
            if released > target:
                return found
            if released == target and row.appid not in seen:
                seen.add(row.appid)
                found.append(row)
        start += len(rows)
        if total and start >= total:
            return found
    log.warning("Stopped after %d search pages; %s may be incomplete.", max_pages, target)
    return found


def filter_content(rows: Iterable[SearchRow], excluded: Iterable[int]) -> list[SearchRow]:
    blocked = set(excluded)
    return [row for row in rows if not blocked.intersection(row.content_descriptors)]


def popularity_ranks(store: SteamStore, appids: set[str], max_pages: int = 12) -> dict[str, int]:
    """Position of each wanted app in Steam's "popular upcoming" list."""
    ranks: dict[str, int] = {}
    if not appids:
        return ranks
    position = 0
    start = 0
    for _ in range(max_pages):
        rows, total = store.search("popularcomingsoon", start=start, category=GAMES_CATEGORY)
        if not rows:
            break
        for row in rows:
            position += 1
            if row.appid in appids and row.appid not in ranks:
                ranks[row.appid] = position
        if len(ranks) == len(appids):
            break
        start += len(rows)
        if total and start >= total:
            break
    return ranks


def to_items(rows: list[SearchRow], ranks: dict[str, int]) -> list[Item]:
    items = [
        Item(
            id=row.appid,
            title=row.title,
            url=row.url,
            date=row.release_date,
            image_url=row.capsule_url,
            rank=ranks.get(row.appid),
            meta={"content_descriptors": row.content_descriptors},
        )
        for row in rows
    ]
    # Ranked games first (most popular on top), unranked keep Steam's order.
    order = {item.id: i for i, item in enumerate(items)}
    items.sort(key=lambda it: (it.rank is None, it.rank or 0, order[it.id]))
    return items


def collect_releases(store: SteamStore, target: date, config: dict[str, Any]) -> list[Item]:
    rows = find_releases(
        store,
        target,
        max_pages=config.get("max_search_pages", 40),
        only_games=config.get("only_games", True),
    )
    total = len(rows)
    rows = filter_content(rows, config.get("excluded_content_descriptors", []))
    log.info("%s: %d games on Steam, %d after content filter", target, total, len(rows))
    ranks = popularity_ranks(store, {r.appid for r in rows}, max_pages=config.get("popularity_pages", 12))
    return to_items(rows, ranks)


def pick_trailer(movies: list[dict[str, Any]]) -> str | None:
    """Best video URL for a game: the store's highlighted trailer first.

    Steam serves trailers as HLS/DASH streams (``hls_h264``); older entries
    may still carry plain MP4 links, which ffmpeg reads just as well.
    """
    ordered = sorted(movies, key=lambda m: not m.get("highlight"))
    for movie in ordered:
        url = movie.get("hls_h264") or (movie.get("mp4") or {}).get("max") or (movie.get("mp4") or {}).get("480")
        if url:
            return url
    return None


def enrich(store: SteamStore, item: Item) -> Item:
    """Add genres, studio, price and the header image from the app's store page.

    Also re-checks the release date, so a game postponed after collection is
    flagged with ``meta["date_changed"] = True``.
    """
    details = store.app_details(item.id)
    if not details:
        item.meta["details_missing"] = True
        return item

    item.title = details.get("name") or item.title
    item.image_url = details.get("header_image") or item.image_url
    screenshots = details.get("screenshots") or []
    trailer = pick_trailer(details.get("movies") or [])
    if trailer:
        item.meta["trailer"] = trailer
    item.meta.update(
        screenshot=(screenshots[0].get("path_full") if screenshots else None),
        genres=[g.get("description") for g in details.get("genres") or [] if g.get("description")],
        developers=details.get("developers") or [],
        publishers=details.get("publishers") or [],
        is_free=bool(details.get("is_free")),
        price=(details.get("price_overview") or {}).get("final_formatted"),
        platforms=[p for p, ok in (details.get("platforms") or {}).items() if ok],
    )
    current = parse_release_date((details.get("release_date") or {}).get("date"))
    item.meta["date_changed"] = item.date is not None and current != item.date
    return item
