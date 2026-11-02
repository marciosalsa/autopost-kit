"""Generic publishing flow: upload -> container -> wait -> (publish) -> clean up."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from autopost_kit.core.publishers.instagram import InstagramClient
from autopost_kit.core.storage import S3Storage

log = logging.getLogger(__name__)


@dataclass
class PublishResult:
    container_id: str
    published: bool
    media_id: str | None = None
    permalink: str | None = None


def publish_reel(
    video: Path | str,
    caption: str,
    instagram: InstagramClient,
    storage: S3Storage,
    confirm: bool = False,
) -> PublishResult:
    """Upload ``video`` and create the Reel. It goes live only when ``confirm`` is True."""
    key, url = storage.upload(video, prefix="reels")
    try:
        container = instagram.create_reel(url, caption)
        instagram.wait_until_ready(container)
    finally:
        # Instagram has its own copy once processing ends (or fails).
        storage.delete(key)

    if not confirm:
        log.info("Dry run: Reel %s is ready but was not published.", container)
        return PublishResult(container_id=container, published=False)

    media_id = instagram.publish(container)
    return PublishResult(container_id=container, published=True, media_id=media_id,
                         permalink=instagram.permalink(media_id))
