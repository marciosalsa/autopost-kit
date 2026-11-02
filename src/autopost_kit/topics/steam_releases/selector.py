"""Choose the games that make it into the post.

Candidates come in popularity order. Games whose title contains a blocked word
are skipped, and so are games whose store page no longer says they release on
the target day. The next most popular game takes the free spot.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Iterable

from autopost_kit.core.models import Item

log = logging.getLogger(__name__)

#: Store "genres" that describe how a game is sold, not what it is.
BADGE_GENRES = {"Early Access": "EARLY ACCESS", "Free To Play": "FREE TO PLAY"}
#: Shown only when a game has no other genre, because almost everything is tagged with it.
FILLER_GENRES = {"Indie"}


def blocked_by(title: str, words: Iterable[str]) -> str | None:
    """Return the blocked word found in ``title`` (whole words, any case), if any."""
    lowered = title.lower()
    for word in words:
        if re.search(rf"(?<!\w){re.escape(word.lower())}(?!\w)", lowered):
            return word
    return None


def display_genres(genres: list[str]) -> list[str]:
    shown = [g for g in genres if g not in BADGE_GENRES]
    meaningful = [g for g in shown if g not in FILLER_GENRES]
    return meaningful or shown


def badge(item: Item) -> str | None:
    if item.meta.get("is_free"):
        return "FREE TO PLAY"
    for genre in item.meta.get("genres", []):
        if genre in BADGE_GENRES:
            return BADGE_GENRES[genre]
    return item.meta.get("price")


def select_top(
    candidates: list[Item],
    count: int,
    blocked_words: Iterable[str],
    enrich: Callable[[Item], Item],
) -> list[Item]:
    blocked_words = list(blocked_words)
    chosen: list[Item] = []
    for item in candidates:
        if len(chosen) == count:
            break
        word = blocked_by(item.title, blocked_words)
        if word:
            log.info("Skipping %r: title contains blocked word %r", item.title, word)
            continue
        item = enrich(item)
        if item.meta.get("details_missing") or item.meta.get("date_changed"):
            log.info("Skipping %r: no store details or release date changed", item.title)
            continue
        # The full name from the store page may contain a word the list title hid.
        if blocked_by(item.title, blocked_words):
            continue
        item.meta["display_genres"] = display_genres(item.meta.get("genres", []))
        item.meta["badge"] = badge(item)
        chosen.append(item)
    for position, item in enumerate(chosen, start=1):
        item.meta["position"] = position
    return chosen
