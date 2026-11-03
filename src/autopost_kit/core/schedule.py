"""Daily runs, configured by the user in ``autopost.yaml``.

The operating system scheduler only calls ``autopost-kit run`` every hour.
This module decides whether a job is due: the local time (in the job's
timezone) has passed the job's ``at`` and that day's post is not done yet.
Each finished run leaves a ``run.json`` in the post folder, so running again
never posts twice, and a run missed while the PC slept is caught up later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

FORMATS = {"reel", "carousel", "both"}
PUBLISH_MODES = {
    "off": "only build the post",
    "review": "build and run Instagram's checks, but do not publish",
    "auto": "build and publish",
}
RUN_FILE = "run.json"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    topic: str
    at: time
    timezone: str
    days_ahead: int = 1
    format: str = "reel"
    publish: str = "review"
    overrides: dict[str, Any] = field(default_factory=dict)

    def run_day(self, now: datetime) -> date:
        """The calendar day, in the job's timezone, that ``now`` belongs to."""
        return now.astimezone(ZoneInfo(self.timezone)).date()

    def target(self, now: datetime) -> date:
        return self.run_day(now) + timedelta(days=self.days_ahead)

    def is_time(self, now: datetime) -> bool:
        return now.astimezone(ZoneInfo(self.timezone)).time() >= self.at

    def topic_overrides(self) -> dict[str, Any]:
        """Settings passed to the topic: the user's overrides plus the job's days_ahead."""
        return {**self.overrides, "days_ahead": self.days_ahead}


@dataclass(frozen=True)
class RunConfig:
    jobs: list[Job]
    music_folder: Path = Path("music")
    output: Path = Path("output")


def _parse_time(value: Any, where: str) -> time:
    try:
        hours, minutes = str(value).split(":")
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        raise ConfigError(f"{where}: 'at' must look like \"00:05\" (24-hour HH:MM), got {value!r}") from None


def _check_choice(value: str, allowed, where: str, key: str) -> str:
    if value not in allowed:
        raise ConfigError(f"{where}: '{key}' must be one of {', '.join(sorted(allowed))}; got {value!r}")
    return value


def parse_config(data: dict[str, Any], known_topics: set[str] | None = None) -> RunConfig:
    if not isinstance(data, dict) or not data.get("jobs"):
        raise ConfigError("autopost.yaml needs a 'jobs' list with at least one job.")
    default_tz = data.get("timezone", "America/Los_Angeles")
    jobs = []
    for n, raw in enumerate(data["jobs"], start=1):
        where = f"jobs[{n}]"
        if not isinstance(raw, dict) or not raw.get("topic"):
            raise ConfigError(f"{where}: every job needs a 'topic'.")
        topic = raw["topic"]
        if known_topics is not None and topic not in known_topics:
            raise ConfigError(f"{where}: unknown topic {topic!r}. Available: {', '.join(sorted(known_topics))}")
        timezone = raw.get("timezone", default_tz)
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ConfigError(f"{where}: unknown timezone {timezone!r} (use names like America/Sao_Paulo)") from None
        days_ahead = raw.get("days_ahead", 1)
        if not isinstance(days_ahead, int) or not 0 <= days_ahead <= 7:
            raise ConfigError(f"{where}: 'days_ahead' must be a whole number from 0 to 7.")
        overrides = raw.get("settings") or {}
        if not isinstance(overrides, dict):
            raise ConfigError(f"{where}: 'settings' must be a mapping of topic settings.")
        jobs.append(Job(
            topic=topic,
            at=_parse_time(raw.get("at", "00:05"), where),
            timezone=timezone,
            days_ahead=days_ahead,
            format=_check_choice(raw.get("format", "reel"), FORMATS, where, "format"),
            publish=_check_choice(raw.get("publish", "review"), PUBLISH_MODES, where, "publish"),
            overrides=overrides,
        ))
    return RunConfig(
        jobs=jobs,
        music_folder=Path(data.get("music_folder", "music")),
        output=Path(data.get("output", "output")),
    )


def load_config(path: Path | str, known_topics: set[str] | None = None) -> RunConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"{path} not found. Copy autopost.example.yaml to {path.name} and edit it.")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path} is not valid YAML: {exc}") from None
    return parse_config(data, known_topics)


# -- run records ---------------------------------------------------------------

def post_folder(config: RunConfig, job: Job, target: date) -> Path:
    return config.output / job.topic / target.isoformat()


def read_run(folder: Path) -> dict[str, Any]:
    path = folder / RUN_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def write_run(folder: Path, **record: Any) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    merged = {**read_run(folder), **record}
    (folder / RUN_FILE).write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")


def already_done(record: dict[str, Any], mode: str) -> bool:
    """A published post is always done; otherwise the job's own step must have finished."""
    if record.get("published"):
        return True
    if mode == "auto":
        return False
    return record.get("mode") == mode and record.get("status") == "ok"
