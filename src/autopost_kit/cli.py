"""Command line entry point: ``autopost-kit <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from autopost_kit import __version__
from autopost_kit.core import pipeline
from autopost_kit.core.models import Item
from autopost_kit.core.output import save_post
from autopost_kit.core.registry import TOPICS, get_topic


def _print_table(target: date, items: list[Item], detailed: int) -> None:
    print(f"\n{target:%b %d, %Y} on Steam: {len(items)} games\n")
    for n, item in enumerate(items, start=1):
        rank = f"#{item.rank}" if item.rank else "-"
        line = f"{n:>3}. {item.title}  [popularity {rank}]"
        if n <= detailed:
            genres = ", ".join(item.meta.get("genres", [])) or "no genre"
            studio = ", ".join(item.meta.get("developers", [])) or "unknown studio"
            line += f"\n       {genres} | {studio}"
            if item.meta.get("date_changed"):
                line += "  (!) release date changed"
        print(line)


def cmd_collect(args: argparse.Namespace) -> int:
    topic = get_topic(args.topic)()
    target = date.fromisoformat(args.date) if args.date else topic.target_date()
    items = topic.collect(target)
    if args.details and hasattr(topic, "enrich"):
        items[: args.details] = topic.enrich(items[: args.details])
    if args.json:
        json.dump([it.to_dict() for it in items], sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        _print_table(target, items, args.details)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    topic = get_topic(args.topic)()
    target = date.fromisoformat(args.date) if args.date else None
    post = pipeline.build(topic, target)
    folder = save_post(post, args.out)
    print(f"\n{len(post.slides)} slides for {post.target:%b %d, %Y} saved to {folder}\n")
    for n, slide in enumerate(post.slides, start=1):
        print(f"  slide_{n:02d}.png  {slide.label}")
    print("\n--- caption.txt ---\n")
    print(post.caption)
    if args.reel:
        _render_reel(folder, args.music_dir, None, topic=topic, slideshow=args.slideshow)
    return 0


def _render_reel(folder, music_dir: str, track: str | None, topic=None, slideshow: bool = False,
                 keep_work: bool = False) -> None:
    from autopost_kit.core.music import MusicLibrary
    from autopost_kit.core.reel import render_reel, render_video_reel

    library = MusicLibrary(music_dir)
    if topic is not None and not slideshow and hasattr(topic, "reel_scenes"):
        manifest = render_video_reel(folder, topic, library, track=track, keep_work=keep_work)
    else:
        manifest = render_reel(folder, library, track=track)
    print(f"\nReel saved to {folder}/{manifest['video']} ({manifest['seconds']:g}s)")
    print(f"Music: {manifest['music']}  (logged as used only when published with --yes)")
    print(f"Caption with music credit: {folder}/{manifest['caption']}")


def cmd_reel(args: argparse.Namespace) -> int:
    from pathlib import Path

    folder = Path(args.post_dir)
    if not folder.is_dir():
        raise SystemExit(f"Post folder not found: {folder}")
    topic = None
    manifest = folder / "post.json"
    if manifest.exists() and not args.slideshow:
        import json

        topic = get_topic(json.loads(manifest.read_text(encoding="utf-8"))["topic"])()
    _render_reel(folder, args.music_dir, args.track, topic=topic, slideshow=args.slideshow,
                 keep_work=args.keep_work)
    return 0


def cmd_music(args: argparse.Namespace) -> int:
    from autopost_kit.core.music import MusicLibrary

    library = MusicLibrary(args.music_dir)
    if args.mark:
        names = {t.name: t for t in library.tracks()}
        if args.mark not in names:
            raise SystemExit(f"Not in {library.folder}/: {args.mark}")
        library.mark_used(args.mark, note="marked by hand")
        print(f"Marked as used: {args.mark}\n")
    tracks = library.tracks()
    if not tracks:
        print(f"No music in {library.folder}/")
        return 0
    used = library.last_used()
    unused = sum(t.name not in used for t in tracks)
    print(f"{len(tracks)} tracks in {library.folder}/, {unused} not used yet\n")
    for t in tracks:
        status = f"used {used[t.name][:10]}" if t.name in used else "new"
        print(f"  [{status:<15}] {t.name}")
    return 0


def _instagram():
    from autopost_kit.core.publishers.instagram import InstagramClient
    from autopost_kit.core.settings import InstagramSettings

    s = InstagramSettings.from_env()
    return InstagramClient(s.access_token, user_id=s.user_id, api_version=s.api_version)


def cmd_instagram_check(_: argparse.Namespace) -> int:
    client = _instagram()
    account = client.account()
    print(f"Connected to @{account.get('username')} (id {account.get('id')})")
    if "followers_count" in account:
        print(f"Followers: {account['followers_count']}  Posts: {account.get('media_count', 0)}")
    quota = client.publishing_quota()
    if quota:
        limit = (quota.get("config") or {}).get("quota_total", "?")
        print(f"API posts in the last 24h: {quota.get('quota_usage', 0)} of {limit}")
    return 0


def cmd_publish_reel(args: argparse.Namespace) -> int:
    from pathlib import Path

    from autopost_kit.core.publish import publish_reel
    from autopost_kit.core.settings import S3Settings
    from autopost_kit.core.storage import S3Storage

    video = Path(args.video)
    if not video.exists():
        raise SystemExit(f"Video not found: {video}")
    caption_path = Path(args.caption) if args.caption else video.with_name("reel_caption.txt")
    if args.caption and not caption_path.exists():
        raise SystemExit(f"Caption not found: {caption_path}")
    caption = caption_path.read_text(encoding="utf-8") if caption_path.exists() else ""
    s3 = S3Settings.from_env()
    result = publish_reel(video, caption, _instagram(), S3Storage(s3.bucket, s3.region), confirm=args.yes)
    if result.published:
        print(f"Published! {result.permalink or result.media_id}")
        _log_music(video, result)
    else:
        print("Dry run OK: Instagram accepted and processed the Reel, but it was NOT published.")
        print("Run again with --yes to publish it for real.")
    return 0


def _log_music(video, result) -> None:
    from autopost_kit.core.music import MusicLibrary
    from autopost_kit.core.reel import music_for_video

    found = music_for_video(video)
    if not found:
        return
    track, folder = found
    MusicLibrary(folder).mark_used(track, video=str(video), media_id=result.media_id or "",
                                   permalink=result.permalink or "")
    print(f"Music logged as used: {track}")


def cmd_topics(_: argparse.Namespace) -> int:
    for name, cls in sorted(TOPICS.items()):
        summary = (cls.__doc__ or "").strip().splitlines()
        print(f"{name:<20} {summary[0] if summary else ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autopost-kit", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="show progress logs")
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="fetch the candidate items for a topic")
    collect.add_argument("topic", help="topic id, e.g. steam_releases")
    collect.add_argument("--date", help="target day (YYYY-MM-DD); default: the topic's next day")
    collect.add_argument("--details", type=int, default=10, help="fetch full details for the top N (default 10, 0 = none)")
    collect.add_argument("--json", action="store_true", help="print JSON instead of a table")
    collect.set_defaults(func=cmd_collect)

    build = sub.add_parser("build", help="collect, select and render a post (nothing is published)")
    build.add_argument("topic", help="topic id, e.g. steam_releases")
    build.add_argument("--date", help="target day (YYYY-MM-DD); default: the topic's next day")
    build.add_argument("--out", default="output", help="output folder (default: output)")
    build.add_argument("--reel", action="store_true", help="also render reel.mp4 with an unused song")
    build.add_argument("--music-dir", default="music", help="music folder (default: music)")
    build.add_argument("--slideshow", action="store_true", help="Reel from the slide images instead of trailers")
    build.set_defaults(func=cmd_build)

    reel_cmd = sub.add_parser("reel", help="render reel.mp4 from a built post, with an unused song")
    reel_cmd.add_argument("post_dir", help="post folder, e.g. output/steam_releases/2026-11-03")
    reel_cmd.add_argument("--music-dir", default="music", help="music folder (default: music)")
    reel_cmd.add_argument("--track", help="use this audio file instead of picking one")
    reel_cmd.add_argument("--slideshow", action="store_true", help="use the slide images instead of trailers")
    reel_cmd.add_argument("--keep-work", action="store_true", help="keep the intermediate clips (_reel_work/)")
    reel_cmd.set_defaults(func=cmd_reel)

    music = sub.add_parser("music", help="list songs and which ones were already used")
    music.add_argument("--music-dir", default="music", help="music folder (default: music)")
    music.add_argument("--mark", metavar="FILE", help="record a song as used (e.g. posted by hand)")
    music.set_defaults(func=cmd_music)

    instagram = sub.add_parser("instagram", help="Instagram account tools")
    ig_sub = instagram.add_subparsers(dest="ig_command", required=True)
    ig_sub.add_parser("check", help="check the token and show the connected account").set_defaults(
        func=cmd_instagram_check)

    publish = sub.add_parser("publish", help="publish media to Instagram (dry run unless --yes)")
    pub_sub = publish.add_subparsers(dest="pub_command", required=True)
    reel = pub_sub.add_parser("reel", help="publish an MP4 as a Reel")
    reel.add_argument("video", help="path to the .mp4 file")
    reel.add_argument("--caption", help="caption text file (default: reel_caption.txt next to the video)")
    reel.add_argument("--yes", action="store_true", help="really publish (without it: everything but publishing)")
    reel.set_defaults(func=cmd_publish_reel)

    topics = sub.add_parser("topics", help="list available topics")
    topics.set_defaults(func=cmd_topics)
    return parser


def main(argv: list[str] | None = None) -> int:
    from autopost_kit.core.settings import load_env

    load_env()
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
