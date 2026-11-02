"""Download remote images once and keep them in a local cache."""

from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path
from typing import Callable

from PIL import Image

from autopost_kit.core.http import PoliteClient

log = logging.getLogger(__name__)

ImageFetcher = Callable[[str], "Image.Image | None"]


class CachedImageFetcher:
    """Callable that returns a PIL image for a URL, or ``None`` if it can't be loaded."""

    def __init__(self, client: PoliteClient, cache_dir: Path | str = ".cache/images") -> None:
        self.client = client
        self.cache_dir = Path(cache_dir)

    def __call__(self, url: str | None) -> Image.Image | None:
        if not url:
            return None
        path = self.cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".img")
        try:
            if not path.exists():
                data = self.client.get_bytes(url)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            image = Image.open(io.BytesIO(path.read_bytes()))
            image.load()
            return image
        except Exception as exc:  # network error, unreadable image...
            log.warning("Could not load image %s: %s", url, exc)
            return None
