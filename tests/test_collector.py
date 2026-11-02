from datetime import date

from autopost_kit.core.models import Item
from autopost_kit.topics.steam_releases import collector
from autopost_kit.topics.steam_releases.parsing import SearchRow

TARGET = date(2026, 11, 3)


def row(appid, released, descids=()):
    return SearchRow(
        appid=str(appid),
        title=f"Game {appid}",
        url=f"https://store.steampowered.com/app/{appid}/",
        release_text=released,
        content_descriptors=list(descids),
    )


class FakeStore:
    """Serves pre-built pages instead of calling Steam."""

    def __init__(self, comingsoon=(), popular=(), details=None):
        self.pages = {"comingsoon": list(comingsoon), "popularcomingsoon": list(popular)}
        self.details = details or {}
        self.calls = []
        self.categories = []

    def search(self, filter_, start=0, count=100, sort_by=None, category=None):
        self.calls.append((filter_, start))
        self.categories.append(category)
        rows, offset = [], 0
        for page in self.pages[filter_]:
            if offset == start:
                rows = page
                break
            offset += len(page)
        total = sum(len(p) for p in self.pages[filter_])
        return rows, total

    def app_details(self, appid):
        return self.details.get(appid)


def test_find_releases_keeps_target_day_and_stops_after_it():
    store = FakeStore(
        comingsoon=[
            [row(1, "Nov 2, 2026"), row(2, "Nov 3, 2026"), row(3, "Coming soon")],
            [row(4, "Nov 3, 2026"), row(5, "Nov 4, 2026"), row(6, "Nov 3, 2026")],
            [row(7, "Nov 3, 2026")],
        ]
    )

    found = collector.find_releases(store, TARGET)

    assert [r.appid for r in found] == ["2", "4"]
    # The third page is never requested: page two already passed the target day.
    assert [c for c in store.calls if c[0] == "comingsoon"] == [("comingsoon", 0), ("comingsoon", 3)]
    # Only full games are requested by default (no soundtracks or demos).
    assert set(store.categories) == {"998"}


def test_find_releases_can_include_every_item_type():
    store = FakeStore(comingsoon=[[row(1, "Nov 3, 2026"), row(2, "Nov 4, 2026")]])

    collector.find_releases(store, TARGET, only_games=False)

    assert store.categories == [None]


def test_find_releases_respects_max_pages():
    pages = [[row(i, "Nov 3, 2026")] for i in range(10)]
    store = FakeStore(comingsoon=pages)

    found = collector.find_releases(store, TARGET, max_pages=3)

    assert len(found) == 3


def test_filter_content_drops_adult_descriptors():
    rows = [row(1, "Nov 3, 2026"), row(2, "Nov 3, 2026", [1, 3, 4, 5]), row(3, "Nov 3, 2026", [2, 5])]

    kept = collector.filter_content(rows, excluded=[3, 4])

    assert [r.appid for r in kept] == ["1", "3"]


def test_popularity_ranks_and_ordering():
    rows = [row(10, "Nov 3, 2026"), row(20, "Nov 3, 2026"), row(30, "Nov 3, 2026")]
    store = FakeStore(popular=[[row(99, "Nov 9, 2026"), row(30, "Nov 3, 2026")], [row(10, "Nov 3, 2026")]])

    ranks = collector.popularity_ranks(store, {"10", "20", "30"}, max_pages=5)
    items = collector.to_items(rows, ranks)

    assert ranks == {"30": 2, "10": 3}
    assert [it.id for it in items] == ["30", "10", "20"]
    assert items[2].rank is None


def test_popularity_ranks_without_candidates_makes_no_request():
    store = FakeStore(popular=[[row(1, "Nov 3, 2026")]])

    assert collector.popularity_ranks(store, set()) == {}
    assert store.calls == []


def test_enrich_adds_details_and_flags_postponed_games():
    item = Item(id="10", title="Game 10", url="u", date=TARGET)
    store = FakeStore(
        details={
            "10": {
                "name": "Lantern Keeper",
                "header_image": "https://example.invalid/header.jpg",
                "genres": [{"id": "1", "description": "Action"}, {"id": "23", "description": "Indie"}],
                "developers": ["Tiny Studio"],
                "publishers": ["Tiny Studio"],
                "is_free": False,
                "price_overview": {"final_formatted": "$9.99"},
                "platforms": {"windows": True, "mac": False, "linux": True},
                "release_date": {"coming_soon": True, "date": "Nov 10, 2026"},
            }
        }
    )

    enriched = collector.enrich(store, item)

    assert enriched.title == "Lantern Keeper"
    assert enriched.image_url == "https://example.invalid/header.jpg"
    assert enriched.meta["genres"] == ["Action", "Indie"]
    assert enriched.meta["developers"] == ["Tiny Studio"]
    assert enriched.meta["price"] == "$9.99"
    assert enriched.meta["platforms"] == ["windows", "linux"]
    assert enriched.meta["date_changed"] is True


def test_enrich_when_steam_has_no_details():
    item = Item(id="404", title="Ghost", url="u", date=TARGET)

    assert collector.enrich(FakeStore(), item).meta["details_missing"] is True
