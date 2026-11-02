"""Command line entry point: ``autopost-kit <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from autopost_kit import __version__
from autopost_kit.core.models import Item
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

    topics = sub.add_parser("topics", help="list available topics")
    topics.set_defaults(func=cmd_topics)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
