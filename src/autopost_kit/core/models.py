"""Data shared between the core and every topic."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Item:
    """One thing a post can talk about: a game, an article, a product...

    The core only relies on the generic fields. Anything topic-specific
    (genres, price, developer...) goes into ``meta``.
    """

    id: str
    title: str
    url: str
    date: date | None = None
    image_url: str | None = None
    rank: int | None = None
    """Popularity position (1 = most popular). ``None`` when unknown."""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["date"] = self.date.isoformat() if self.date else None
        return data
