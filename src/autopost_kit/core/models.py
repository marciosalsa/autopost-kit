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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        values = dict(data)
        values["date"] = date.fromisoformat(values["date"]) if values.get("date") else None
        return cls(**values)


@dataclass
class Slide:
    """One image of a carousel. ``label`` says what it shows (e.g. ``cover``, ``#5``)."""

    label: str
    image: Any  # PIL.Image.Image; kept loose so models.py does not import Pillow


@dataclass
class Post:
    """A ready-to-publish carousel: slides in order plus the caption."""

    topic: str
    target: date
    slides: list[Slide]
    caption: str
    items: list[Item] = field(default_factory=list)
    total: int | None = None
    """How many candidates there were before selection (e.g. games released that day)."""

    #: Instagram accepts at most 10 images in a carousel.
    MAX_SLIDES = 10

    def __post_init__(self) -> None:
        if not 1 <= len(self.slides) <= self.MAX_SLIDES:
            raise ValueError(f"A carousel needs 1 to {self.MAX_SLIDES} slides, got {len(self.slides)}.")
