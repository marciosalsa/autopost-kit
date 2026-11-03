from datetime import date, datetime, time, timezone
from types import SimpleNamespace

import pytest

from autopost_kit.core import daily, schedule
from autopost_kit.core.models import Item, Post, Slide
from autopost_kit.core.schedule import ConfigError
from autopost_kit.core.topic import deep_merge

UTC = timezone.utc


def config(tmp_path, **job):
    data = {"timezone": "America/Los_Angeles", "output": str(tmp_path / "out"),
            "jobs": [{"topic": "steam_releases", **job}]}
    return schedule.parse_config(data, known_topics={"steam_releases"})


# --- config -------------------------------------------------------------------

def test_defaults_and_overrides(tmp_path):
    cfg = config(tmp_path, settings={"top_n": 3, "reel": {"clip_seconds": 7}})
    job = cfg.jobs[0]

    assert (job.at, job.days_ahead, job.format, job.publish) == (time(0, 5), 1, "reel", "review")
    assert job.topic_overrides() == {"top_n": 3, "reel": {"clip_seconds": 7}, "days_ahead": 1}


@pytest.mark.parametrize("job, message", [
    ({"at": "25:99"}, "'at' must look like"),
    ({"publish": "yes"}, "'publish' must be one of"),
    ({"format": "story"}, "'format' must be one of"),
    ({"timezone": "Mars/Base"}, "unknown timezone"),
    ({"days_ahead": 30}, "'days_ahead'"),
    ({"topic": "nope"}, "unknown topic"),
])
def test_bad_config_explains_the_problem(tmp_path, job, message):
    with pytest.raises(ConfigError, match=message):
        config(tmp_path, **job)


def test_missing_file_points_to_the_example(tmp_path):
    with pytest.raises(ConfigError, match="autopost.example.yaml"):
        schedule.load_config(tmp_path / "autopost.yaml")


def test_deep_merge_keeps_unchanged_nested_keys():
    base = {"top_n": 5, "reel": {"cover_seconds": 3.7, "clip_seconds": 11}}

    assert deep_merge(base, {"reel": {"clip_seconds": 7}}) == {"top_n": 5, "reel": {"cover_seconds": 3.7, "clip_seconds": 7}}


# --- timing -------------------------------------------------------------------

def test_job_time_follows_its_timezone(tmp_path):
    job = config(tmp_path, at="00:05").jobs[0]
    before = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)  # 00:00 in Los Angeles (PST)
    after = datetime(2026, 11, 3, 8, 10, tzinfo=UTC)  # 00:10

    assert not job.is_time(before)
    assert job.is_time(after)
    assert job.target(after) == date(2026, 11, 4)


# --- running ------------------------------------------------------------------

class FakeTopic:
    name = "steam_releases"

    def target_date(self):
        return date(2026, 11, 4)

    def collect(self, target):
        return [Item(id="1", title="Game", url="u", date=target)]

    def select(self, items):
        return items

    def build_post(self, target, selected, total):
        from PIL import Image

        return Post(topic=self.name, target=target, slides=[Slide("cover", Image.new("RGB", (10, 10)))],
                    caption="c", items=selected, total=total)


def run(cfg, now, calls, published=True, **kwargs):
    def publish(video, confirm):
        calls.append(("publish", confirm))
        return SimpleNamespace(published=confirm and published, permalink="https://ig/reel/1" if confirm else None)

    def reel(folder, topic):
        calls.append(("reel",))
        (folder / "reel.mp4").write_bytes(b"")
        return {"video": "reel.mp4"}

    return daily.run_jobs(cfg, lambda job: FakeTopic(), publish, reel, now=now, **kwargs)


NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)  # 01:00 in Los Angeles


def test_auto_publishes_once_per_day(tmp_path):
    cfg, calls = config(tmp_path, publish="auto"), []

    first = run(cfg, NOW, calls)
    second = run(cfg, NOW, calls)

    assert first[0].status == "published" and first[0].permalink == "https://ig/reel/1"
    assert second[0].status.startswith("skipped") and "already done" in second[0].status
    assert calls.count(("publish", True)) == 1


def test_too_early_does_nothing(tmp_path):
    cfg, calls = config(tmp_path, at="06:00"), []

    assert run(cfg, NOW, calls)[0].status.startswith("skipped: runs at 06:00")
    assert calls == []


def test_review_checks_without_publishing_and_auto_can_follow(tmp_path):
    calls = []
    assert run(config(tmp_path, publish="review"), NOW, calls)[0].status == "checked"
    assert ("publish", False) in calls

    # Switching the same day to auto still publishes.
    assert run(config(tmp_path, publish="auto"), NOW, calls)[0].status == "published"


def test_off_only_builds(tmp_path):
    calls = []

    result = run(config(tmp_path, publish="off", format="carousel"), NOW, calls)[0]

    assert result.status == "built" and calls == []
    assert (result.folder / "slide_01.png").exists()


def test_failure_is_recorded_and_retried_next_time(tmp_path):
    cfg = config(tmp_path, publish="auto")

    def broken(job):
        raise RuntimeError("Steam is down")

    first = daily.run_jobs(cfg, broken, None, None, now=NOW)
    assert first[0].status == "failed: Steam is down"
    assert schedule.read_run(first[0].folder)["status"] == "failed"

    assert run(cfg, NOW, [])[0].status == "published"
