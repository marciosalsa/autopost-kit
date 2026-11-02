"""The Steam releases topic: what the engine posts about for @tomorrowonsteam."""

from __future__ import annotations

from datetime import date
from typing import Any

from autopost_kit.core.dates import target_date
from autopost_kit.core.http import PoliteClient
from autopost_kit.core.models import Item
from autopost_kit.core.topic import Topic
from autopost_kit.topics.steam_releases import collector
from autopost_kit.topics.steam_releases.steam_store import SteamStore


class SteamReleasesTopic(Topic):
    """Games released on Steam tomorrow (Pacific time)."""

    name = "steam_releases"
    config_package = "autopost_kit.topics.steam_releases"

    def __init__(self, overrides: dict[str, Any] | None = None, store: SteamStore | None = None) -> None:
        super().__init__(overrides)
        self.store = store or SteamStore(
            PoliteClient(min_interval=self.config.get("request_interval_seconds", 1.5)),
            country=self.config.get("country", "us"),
            language=self.config.get("language", "english"),
        )

    def target_date(self) -> date:
        return target_date(self.config["timezone"], self.config.get("days_ahead", 1))

    def collect(self, target: date) -> list[Item]:
        return collector.collect_releases(self.store, target, self.config)

    def enrich(self, items: list[Item]) -> list[Item]:
        return [collector.enrich(self.store, item) for item in items]
