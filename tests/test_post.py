from datetime import date

from PIL import Image

from autopost_kit.core import pipeline
from autopost_kit.core.models import Item, Post
from autopost_kit.core.output import save_post
from autopost_kit.topics.steam_releases import selector
from autopost_kit.topics.steam_releases.topic import SteamReleasesTopic

TARGET = date(2026, 11, 3)


def game(n, title=None, genres=("Action", "Indie"), **meta):
    return Item(
        id=str(n),
        title=title or f"Game {n}",
        url=f"https://store.steampowered.com/app/{n}/",
        date=TARGET,
        image_url=f"https://example.invalid/{n}/header.jpg",
        rank=n,
        meta={"genres": list(genres), "developers": [f"Studio {n}"], **meta},
    )


def fake_fetch(url):
    if not url:
        return None
    # Screenshots are wide 16:9, headers are short banners.
    size = (1920, 1080) if "shot" in url else (460, 215)
    return Image.new("RGB", size, (40, 90, 160))


def enrich_ok(item):
    item.meta.setdefault("screenshot", f"https://example.invalid/{item.id}/shot.jpg")
    item.meta.setdefault("date_changed", False)
    return item


# --- selection -------------------------------------------------------------

def test_blocked_by_matches_whole_words_only():
    words = ["sex", "great again", "abuse"]

    assert selector.blocked_by("CHILD ABUSE HEROES", words) == "abuse"
    assert selector.blocked_by("Make the World Great Again", words) == "great again"
    assert selector.blocked_by("Sussex Farm Simulator", words) is None  # "sex" inside a word


def test_display_genres_hides_badges_and_filler():
    assert selector.display_genres(["Action", "Indie", "Strategy", "Early Access"]) == ["Action", "Strategy"]
    assert selector.display_genres(["Indie"]) == ["Indie"]
    assert selector.display_genres(["Indie", "Free To Play"]) == ["Indie"]


def test_badge_priority():
    assert selector.badge(game(1, genres=["Action", "Early Access"])) == "EARLY ACCESS"
    assert selector.badge(game(2, is_free=True)) == "FREE TO PLAY"
    assert selector.badge(game(3, price="$9.99")) == "$9.99"
    assert selector.badge(game(4)) is None


def test_select_top_skips_blocked_and_postponed_games():
    candidates = [game(1), game(2, title="Child Abuse Heroes"), game(3, date_changed=True), game(4), game(5), game(6)]

    chosen = selector.select_top(candidates, count=3, blocked_words=["abuse"], enrich=enrich_ok)

    assert [g.id for g in chosen] == ["1", "4", "5"]
    assert [g.meta["position"] for g in chosen] == [1, 2, 3]


def test_select_top_only_enriches_what_it_needs():
    enriched = []

    def enrich(item):
        enriched.append(item.id)
        return enrich_ok(item)

    selector.select_top([game(n) for n in range(1, 50)], count=5, blocked_words=[], enrich=enrich)

    assert enriched == ["1", "2", "3", "4", "5"]


# --- building the post -----------------------------------------------------

class FakeTopic(SteamReleasesTopic):
    def __init__(self, items):
        super().__init__(store=object(), fetch_image=fake_fetch)
        self._items = items

    def collect(self, target):
        return self._items

    def select(self, items):
        return selector.select_top(items, count=5, blocked_words=[], enrich=enrich_ok)


def test_build_makes_cover_plus_countdown():
    items = [game(n, title=name) for n, name in enumerate(
        ["Gravity Dogs", "Boost", "Figure It", "Mayday: The Survival Island With A Long Name", "Sabado", "Extra"],
        start=1,
    )]
    items[0].meta["genres"] = ["Action", "Indie", "Strategy", "Early Access"]

    post = pipeline.build(FakeTopic(items), TARGET)

    assert [s.label for s in post.slides] == ["cover", "#5", "#4", "#3", "#2", "#1"]
    assert all(s.image.size == (1080, 1350) for s in post.slides)
    assert "6 new games launch tomorrow" in post.caption
    assert "1. Gravity Dogs: Action · Strategy · by Studio 1" in post.caption
    assert "+1 more on Steam tomorrow." in post.caption
    assert "#steam" in post.caption


def test_slide_renders_without_any_image():
    topic = FakeTopic([game(1)])
    topic.fetch_image = lambda url: None

    post = pipeline.build(topic, TARGET)

    assert len(post.slides) == 2


def test_post_rejects_more_than_ten_slides():
    import pytest

    with pytest.raises(ValueError):
        Post(topic="t", target=TARGET, slides=[object()] * 11, caption="")


def test_save_post_writes_slides_caption_and_manifest(tmp_path):
    post = pipeline.build(FakeTopic([game(1), game(2)]), TARGET)

    folder = save_post(post, tmp_path)

    assert sorted(p.name for p in folder.iterdir()) == ["caption.txt", "post.json", "slide_01.png", "slide_02.png", "slide_03.png"]
    assert folder == tmp_path / "steam_releases" / "2026-11-03"
