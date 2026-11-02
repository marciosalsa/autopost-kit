"""The generic flow every topic goes through."""

from __future__ import annotations

import logging
from datetime import date

from autopost_kit.core.models import Post
from autopost_kit.core.topic import Topic

log = logging.getLogger(__name__)


def build(topic: Topic, target: date | None = None) -> Post:
    """collect -> select -> build_post. Nothing is published here."""
    target = target or topic.target_date()
    items = topic.collect(target)
    if not items:
        raise SystemExit(f"No items found for {target}; nothing to post.")
    selected = topic.select(items)
    if not selected:
        raise SystemExit(f"{len(items)} items found for {target}, but none passed selection.")
    log.info("%s: %d collected, %d selected", target, len(items), len(selected))
    return topic.build_post(target, selected, total=len(items))
