"""A polite HTTP client: spaced-out requests, retries with backoff, clear user agent."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import requests

from autopost_kit import __version__

log = logging.getLogger(__name__)

USER_AGENT = f"autopost-kit/{__version__} (+https://github.com/marciosalsa/autopost-kit)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class PoliteClient:
    """Wraps ``requests.Session`` so topics never hammer a public site.

    * waits at least ``min_interval`` seconds between requests
    * retries on 429/5xx and network errors with exponential backoff
    """

    def __init__(
        self,
        min_interval: float = 1.5,
        max_retries: int = 3,
        backoff: float = 5.0,
        timeout: float = 20.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.backoff = backoff
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            elapsed = self._clock() - self._last_request
            if elapsed < self.min_interval:
                self._sleep(self.min_interval - elapsed)
        self._last_request = self._clock()

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        attempt = 0
        while True:
            self._wait_turn()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                if response.status_code not in RETRY_STATUS:
                    response.raise_for_status()
                    return response.json()
                error: Exception = requests.HTTPError(f"HTTP {response.status_code}")
            except (requests.ConnectionError, requests.Timeout) as exc:
                error = exc

            attempt += 1
            if attempt > self.max_retries:
                raise error
            delay = self.backoff * 2 ** (attempt - 1)
            log.warning("Request to %s failed (%s); retry %d in %.0fs", url, error, attempt, delay)
            self._sleep(delay)
