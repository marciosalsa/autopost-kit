from datetime import date, datetime, timezone

import pytest
import requests

from autopost_kit.core.dates import target_date
from autopost_kit.core.http import PoliteClient
from autopost_kit.topics.steam_releases.topic import SteamReleasesTopic


def test_target_date_uses_the_topic_timezone():
    # 03:00 UTC on Nov 2 is still Nov 1 (19:00) in Los Angeles.
    now = datetime(2026, 11, 2, 3, 0, tzinfo=timezone.utc)

    assert target_date("America/Los_Angeles", 1, now=now) == date(2026, 11, 2)
    assert target_date("UTC", 1, now=now) == date(2026, 11, 3)


def test_topic_config_loads_defaults_and_overrides():
    topic = SteamReleasesTopic(overrides={"days_ahead": 2}, store=object())

    assert topic.config["timezone"] == "America/Los_Angeles"
    assert topic.config["excluded_content_descriptors"] == [3, 4]
    assert topic.config["days_ahead"] == 2


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)

    def get(self, url, params=None, timeout=None):
        return self.responses.pop(0)


def test_polite_client_retries_then_succeeds():
    sleeps = []
    session = FakeSession([FakeResponse(429), FakeResponse(503), FakeResponse(200, {"ok": True})])
    client = PoliteClient(min_interval=0, backoff=1, session=session, sleep=sleeps.append)

    assert client.get_json("https://example.invalid") == {"ok": True}
    assert sleeps == [1, 2]
    assert "autopost-kit" in session.headers["User-Agent"]


def test_polite_client_gives_up_after_max_retries():
    session = FakeSession([FakeResponse(500)] * 3)
    client = PoliteClient(min_interval=0, max_retries=2, backoff=0, session=session, sleep=lambda s: None)

    with pytest.raises(requests.HTTPError):
        client.get_json("https://example.invalid")


def test_polite_client_spaces_out_requests():
    sleeps, now = [], [100.0]
    session = FakeSession([FakeResponse(200, {}), FakeResponse(200, {})])
    client = PoliteClient(min_interval=1.5, session=session, sleep=sleeps.append, clock=lambda: now[0])

    client.get_json("https://example.invalid")
    now[0] += 0.5
    client.get_json("https://example.invalid")

    assert sleeps == [1.0]
