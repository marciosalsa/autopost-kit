"""``autopost-kit run``: carry out every due job from ``autopost.yaml``."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from autopost_kit.core import pipeline, schedule
from autopost_kit.core.output import save_post
from autopost_kit.core.schedule import Job, RunConfig

log = logging.getLogger(__name__)


@dataclass
class JobResult:
    job: Job
    status: str  # "skipped: ...", "built", "checked", "published", "failed: ..."
    folder: Path | None = None
    permalink: str | None = None


def run_jobs(
    config: RunConfig,
    make_topic: Callable[[Job], object],
    publish: Callable[[Path, bool], object],
    render_reel: Callable[[Path, object], dict],
    now: datetime | None = None,
    force: bool = False,
    only: str | None = None,
) -> list[JobResult]:
    """Run due jobs. ``publish(video, confirm)`` and ``render_reel(folder, topic)`` are injected."""
    now = now or datetime.now(timezone.utc)
    results = []
    for job in config.jobs:
        if only and job.topic != only:
            continue
        target = job.target(now)
        folder = schedule.post_folder(config, job, target)
        record = schedule.read_run(folder)

        if not force and not job.is_time(now):
            results.append(JobResult(job, f"skipped: runs at {job.at:%H:%M} {job.timezone}", folder))
            continue
        if not force and schedule.already_done(record, job.publish):
            results.append(JobResult(job, f"skipped: {target} already done", folder, record.get("permalink")))
            continue

        try:
            results.append(_run_one(job, target, config, make_topic, publish, render_reel))
        except (Exception, SystemExit) as exc:  # one failing job must not stop the others
            log.exception("Job %s for %s failed", job.topic, target)
            schedule.write_run(folder, mode=job.publish, status="failed", error=str(exc),
                               finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            results.append(JobResult(job, f"failed: {exc}", folder))
    return results


def _run_one(job, target, config, make_topic, publish, render_reel) -> JobResult:
    topic = make_topic(job)
    post = pipeline.build(topic, target)
    folder = save_post(post, config.output)
    log.info("%s: post for %s saved to %s", job.topic, target, folder)

    video = None
    if job.format in {"reel", "both"}:
        manifest = render_reel(folder, topic)
        video = folder / manifest["video"]

    status, permalink = "built", None
    if job.publish != "off" and video is not None:
        result = publish(video, job.publish == "auto")
        if getattr(result, "published", False):
            status, permalink = "published", getattr(result, "permalink", None)
        else:
            status = "checked"
    elif job.publish != "off":
        log.warning("%s: publishing carousels is not supported yet; the post was only built.", job.topic)

    schedule.write_run(folder, mode=job.publish, status="ok", result=status, published=status == "published",
                       permalink=permalink, finished_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    return JobResult(job, status, folder, permalink)
