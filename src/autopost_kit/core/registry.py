"""Where topics are registered. Adding a subject = adding one line here."""

from __future__ import annotations

from autopost_kit.core.topic import Topic
from autopost_kit.topics.steam_releases.topic import SteamReleasesTopic

TOPICS: dict[str, type[Topic]] = {
    SteamReleasesTopic.name: SteamReleasesTopic,
}


def get_topic(name: str) -> type[Topic]:
    try:
        return TOPICS[name]
    except KeyError:
        available = ", ".join(sorted(TOPICS))
        raise SystemExit(f"Unknown topic '{name}'. Available: {available}") from None
