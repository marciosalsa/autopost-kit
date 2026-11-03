"""The Steam releases topic: what the engine posts about for @tomorrowonsteam."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from autopost_kit.core import video
from autopost_kit.core.video import Scene

from autopost_kit.core.dates import target_date
from autopost_kit.core.http import PoliteClient
from autopost_kit.core.i18n import fill, load_strings
from autopost_kit.core.images import CachedImageFetcher, ImageFetcher
from autopost_kit.core.models import Item, Post
from autopost_kit.core.render import Theme
from autopost_kit.core.topic import Topic
from autopost_kit.topics.steam_releases import collector, layout, selector
from autopost_kit.topics.steam_releases.steam_store import SteamStore

log = logging.getLogger(__name__)


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
                    caption=self.caption(strings, target, total, selected), items=selected, total=total)

    # -- Reel with trailers ---------------------------------------------------

    def reel_lengths(self, post: dict) -> list[float]:
        """Wanted seconds per scene: the cover, then one per game (before snapping to the beat)."""
        reel = self.config.get("reel", {})
        return [reel.get("cover_seconds", 3.7)] + [reel.get("clip_seconds", 11.0)] * len(post["items"])

    def reel_scenes(self, post: dict, lengths: list[float], work: Path) -> list[Scene]:
        """Cover + countdown #N..#1, each game over a stretch of its trailer."""
        strings = load_strings(self.config_package, self.config.get("language", "en"))
        target = date.fromisoformat(post["target"])
        games: list[Item] = post["items"]
        total = post.get("total") or len(games)
        work.mkdir(parents=True, exist_ok=True)

        cover = work / "cover.png"
        layout.render_reel_cover(self.theme, strings, target, total, games).save(cover)
        scenes = [Scene(label="cover", seconds=lengths[0], still=cover)]

        for rank, seconds in zip(range(len(games), 0, -1), lengths[1:]):
            game = games[rank - 1]
            overlay = work / f"overlay_{rank}.png"
            layout.render_reel_overlay(self.theme, strings, target, game, rank, self.fetch_image).save(overlay)
            clip = self._clip_for(game, rank, seconds, work)
            scenes.append(Scene(label=f"#{rank} {game.title}", seconds=seconds, overlay=overlay, clip=clip,
                                video_y=layout.REEL_VIDEO_Y))
        return scenes

    def _clip_for(self, game: Item, rank: int, seconds: float, work: Path) -> Path | None:
        trailer = game.meta.get("trailer")
        if trailer:
            try:
                return video.fetch_clip(trailer, work / f"clip_{rank}.mp4", seconds + 0.5)
            except Exception as exc:  # stream offline, ffmpeg error...
                log.warning("No trailer clip for %s (%s); using a screenshot.", game.title, exc)
        image = self.fetch_image(game.meta.get("screenshot")) or self.fetch_image(game.image_url)
        if image is None:
            raise RuntimeError(f"No trailer or image for {game.title}")
        path = work / f"still_{rank}.jpg"
        image.convert("RGB").save(path, quality=92)
        return path

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
