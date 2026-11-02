from datetime import date
from pathlib import Path

import pytest

from autopost_kit.topics.steam_releases.parsing import parse_release_date, parse_search_html

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Nov 3, 2026", date(2026, 11, 3)),
        ("  Nov 3, 2026   ", date(2026, 11, 3)),
        ("3 Nov, 2026", date(2026, 11, 3)),
        ("November 3, 2026", date(2026, 11, 3)),
        ("Coming soon", None),
        ("To be announced", None),
        ("Q4 2026", None),
        ("November 2026", None),
        ("2026", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_release_date(text, expected):
    assert parse_release_date(text) == expected


def test_parse_search_html_reads_each_row():
    rows = parse_search_html((FIXTURES / "search_row.html").read_text("utf-8"))

    assert [r.appid for r in rows] == ["1000001", "1000002"]

    first = rows[0]
    assert first.title == "Lantern Keeper & Friends"
    assert first.url == "https://store.steampowered.com/app/1000001/Lantern_Keeper/"
    assert first.release_text == "Nov 3, 2026"
    assert first.release_date == date(2026, 11, 3)
    assert first.capsule_url.endswith("capsule_231x87.jpg?t=1")
    assert first.content_descriptors == []

    second = rows[1]
    assert second.release_date is None
    assert second.content_descriptors == [1, 3, 4, 5]


def test_parse_search_html_empty():
    assert parse_search_html("") == []
