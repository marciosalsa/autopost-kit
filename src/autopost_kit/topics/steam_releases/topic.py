"""The Steam releases topic: what the engine posts about for @tomorrowonsteam."""

from __future__ import annotations

from datetime import date
from typing import Any

from autopost_kit.core.dates import target_date
from autopost_kit.core.http import PoliteClient
from autopost_kit.core.i18n import fill, load_strings
from autopost_kit.core.images import CachedImageFetcher, ImageFetcher
from autopost_kit.core.models import Item, Post
from autopost_kit.core.render import Theme
from autopost_kit.core.topic import Topic
from autopost_kit.topics.steam_releases import collector, layout, selector
from autopost_kit.topics.steam_releases.steam_store import SteamStore


class SteamReleasesTopic(Topic):
    """Games released on Steam tomorrow (Pacific time)."""

    name = "steam_releases"
    config_package = "autopost_kit.topics.steam_releases"

    def __init__(
        self,
        overrides: dict[str, Any] | None = None,
        store: SteamStore | None = None,
        fetch_image: ImageFetcher | None = None,
    ) -> None:
        super().__init__(overrides)
        client = PoliteClient(min_interval=self.config.get("request_interval_seconds", 1.5))
        self.store = store or SteamStore(
            client,
            country=self.config.get("country", "us"),
            language=self.config.get("store_language", "english"),
        )
        self.fetch_image = fetch_image or CachedImageFetcher(PoliteClient(min_interval=0.2))
        self.theme = Theme.from_config(self.config.get("theme"))

    def target_date(self) -> date:
        return target_date(self.config["timezone"], self.config.get("days_ahead", 1))

    def collect(self, target: date) -> list[Item]:
        return collector.collect_releases(self.store, target, self.config)

    def enrich(self, items: list[Item]) -> list[Item]:
        return [collector.enrich(self.store, item) for item in items]

    def select(self, items: list[Item]) -> list[Item]:
        return selector.select_top(
            items,
            count=self.config.get("top_n", 5),
            blocked_words=self.config.get("blocked_words", []),
            enrich=lambda item: collector.enrich(self.store, item),
        )

    def build_post(self, target: date, selected: list[Item], total: int) -> Post:
        strings = load_strings(self.config_package, self.config.get("language", "en"))
        slides = [layout.render_cover(self.theme, strings, target, total, selected)]
        for rank in range(len(selected), 0, -1):  # countdown: N ... 1
            slides.append(layout.render_game(self.theme, strings, target, selected[rank - 1], rank, self.fetch_image))
        return Post(topic=self.name, target=target, slides=slides,
                    caption=self.caption(strings, target, total, selected), items=selected)

    def caption(self, strings: dict[str, str], target: date, total: int, selected: list[Item]) -> str:
        lines = "\n".join(
            fill(
                strings["caption_line"],
                position=item.meta.get("position", n),
                name=item.title,
                genres=" · ".join(item.meta.get("display_genres", [])[:2]) or "Game",
                studio=", ".join(item.meta.get("developers", [])[:2]) or "unknown studio",
            )
            for n, item in enumerate(selected, start=1)
        )
        more = total - len(selected)
        return fill(
            strings["caption"],
            date_long=f"{target:%B} {target.day}, {target.year}",
            total=total,
            count=len(selected),
            lines=lines,
            more_line=fill(strings["caption_more"], more=more) if more > 0 else "",
            hashtags=self.config.get("hashtags", ""),
        ).strip() + "\n"
