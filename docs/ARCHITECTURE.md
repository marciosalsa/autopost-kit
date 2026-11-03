# Architecture

This document describes where autopost-kit is today, where it is going, and
the step-by-step plan to get there without breaking the daily Reel.

## Goals

- **The core never knows about a topic.** Steam is one plugin among future ones
  (other stores, other subjects). Adding a topic means installing a package.
- **Swappable infrastructure.** Instagram today, YouTube Shorts tomorrow; S3
  today, a temporary tunnel as a free alternative. Each is an adapter behind a port.
- **Every daily run is safe to repeat.** A crash or a second run never posts twice.
- **Testable without the network.** Domain and use cases run on fakes; adapters
  have their own focused tests.

## Where we are (v0.1)

```
src/autopost_kit/
├── cli.py                  # argument parsing + orchestration + publishing logic
├── core/                   # models, topic ABC, http, render, video, beats, music, s3, instagram, registry
└── topics/steam_releases/  # collector, Steam client, parsing, selector, layout, topic
```

It works end to end (collect → select → render carousel / Reel → publish), with
59 tests. The problems below are what makes the next topics and networks costly.

| # | Problem | Principle | Where |
|---|---------|-----------|-------|
| 1 | The core imports the Steam topic to register it, so the core depends on a plugin. | Dependency Inversion, dependency rule | `core/registry.py` |
| 2 | The CLI decides how to render and publish (`hasattr(topic, "reel_scenes")`, music logging, caption lookup). | Single Responsibility | `cli.py` (245 lines) |
| 3 | Optional abilities are discovered with `hasattr` instead of declared interfaces. | Interface Segregation | `cli.py` |
| 4 | The Steam topic builds its own HTTP client, image cache and store inside `__init__`. | Dependency Inversion; no composition root | `topics/steam_releases/topic.py` |
| 5 | `publish_reel` takes the concrete `InstagramClient` and `S3Storage`. A second network or host means editing it. | Open/Closed | `core/publish.py` |
| 6 | ffmpeg, librosa, Pillow, boto3 and requests all live in `core/`, next to the models. | Separation of concerns (domain vs infrastructure) | `core/` |
| 7 | Topic data travels in an untyped `Item.meta` dict (17 different keys). Typos fail at runtime. | Explicit domain model | `collector.py`, `selector.py`, `layout.py` |
| 8 | Config is a raw dict from YAML, read with `.get(..., default)` all over the code. | Fail fast, single source of defaults | `topic.yaml` readers |
| 9 | `SystemExit` is raised from the core (`pipeline.py`, `registry.py`, `settings.py`). | Core should raise domain errors; only the CLI maps them to exit codes | core modules |
| 10 | Only the music has a history (`used.json`). Nothing records which posts went out. | Idempotency | publishing |

## Where we are going

Ports and adapters (hexagonal architecture), in a monorepo with two packages.

```
packages/
├── autopost-kit/                      # the engine (distribution: autopost-kit)
│   └── src/autopost_kit/
│       ├── domain/                    # pure Python: no I/O, no third-party imports
│       │   ├── content.py             # Item, Post, Slide, Scene, Timeline
│       │   └── errors.py              # NothingToPost, PublishFailed, ConfigError...
│       ├── ports/                     # Protocols the application depends on
│       │   ├── topic.py               # ContentSource, Selector, CarouselComposer, ReelComposer
│       │   ├── publishing.py          # Publisher, MediaHost
│       │   ├── media.py               # ImageFetcher, ClipFetcher, VideoRenderer, BeatAnalyzer
│       │   ├── music.py               # MusicLibrary
│       │   └── history.py             # PostHistory
│       ├── application/               # use cases, one per file, only talk to ports
│       │   ├── build_post.py
│       │   ├── render_reel.py
│       │   ├── publish_post.py
│       │   └── daily_run.py           # build + render + publish, idempotent per (topic, date)
│       ├── adapters/                  # the outside world
│       │   ├── http/polite_client.py
│       │   ├── images/cached_fetcher.py
│       │   ├── render/pillow.py       # drawing primitives (public SDK for topics)
│       │   ├── video/ffmpeg.py
│       │   ├── audio/librosa_beats.py
│       │   ├── music/folder_library.py
│       │   ├── storage/s3.py
│       │   ├── publishers/instagram.py
│       │   └── history/sqlite.py
│       ├── config/                    # typed settings (.env) + topic config validation
│       ├── plugins.py                 # topic discovery through entry points
│       ├── bootstrap.py               # composition root: the only place that wires adapters
│       └── cli/                       # thin commands: parse args, call a use case, print
└── autopost-topic-steam/              # the first plugin (distribution: autopost-topic-steam)
    └── src/autopost_topic_steam/
        ├── plugin.py                  # factory, registered under "autopost_kit.topics"
        ├── models.py                  # GameRelease (typed: genres, studio, trailer, badge...)
        ├── store/                     # Steam client + HTML/JSON parsing
        ├── collector.py, selector.py
        ├── templates/                 # carousel.py, reel.py (use the render SDK)
        ├── config.py                  # SteamTopicConfig (validated topic.yaml)
        └── topic.yaml, locales/
```

### Dependency rule

```
cli, bootstrap ─▶ adapters ─▶ application ─▶ ports ─▶ domain
                                    ▲
autopost-topic-steam ───────────────┘  (depends only on domain, ports and the render SDK)
```

Arrows point to what a layer may import. Nothing points outward: the domain
never imports an adapter, and the engine never imports a plugin. An
import-linter contract in CI enforces this.

### Key interfaces (sketch)

```python
class ContentSource(Protocol):
    name: str
    def target_date(self, now: datetime) -> date: ...
    def collect(self, target: date) -> list[Item]: ...

class Selector(Protocol):
    def select(self, items: list[Item]) -> list[Item]: ...

class ReelComposer(Protocol):          # optional: a topic that can make Reels implements it
    def reel_lengths(self, post: Post) -> list[float]: ...
    def reel_scenes(self, post: Post, timeline: Timeline, assets: ClipFetcher) -> list[Scene]: ...

class Publisher(Protocol):             # Instagram now, YouTube Shorts later
    def publish_video(self, media: HostedMedia, caption: str, *, dry_run: bool) -> PublishResult: ...

class MediaHost(Protocol):             # S3 now, a temporary tunnel as a free option
    def share(self, path: Path) -> AbstractContextManager[HostedMedia]: ...
```

A topic plugin exposes a factory that receives what it needs (HTTP client,
image fetcher, config) from the composition root, instead of building them:

```toml
# packages/autopost-topic-steam/pyproject.toml
[project.entry-points."autopost_kit.topics"]
steam_releases = "autopost_topic_steam.plugin:create"
```

## Decisions

- **ADR-001: Ports and adapters.** The domain and use cases are tested with
  fakes; infrastructure is replaceable. Cost: more files and indirection, which
  is worth it because a second topic and a second network are on the roadmap.
- **ADR-002: Plugins through Python entry points.** Standard packaging, no custom
  loader; `pip install autopost-topic-xyz` is enough for the CLI to list it.
- **ADR-003: Monorepo with a uv workspace.** One repository, two distributions,
  one CI. Topics can still be split into their own repositories later.
- **ADR-004: Protocols over abstract base classes.** Structural typing keeps
  plugins decoupled from engine classes; mypy checks conformance.
- **ADR-005: Keep ffmpeg as a subprocess.** It is fast, handles HLS trailers and
  is already required; a Python video library would add weight for no gain.
- **ADR-006: Instagram API with Unified Login + S3 pre-signed links.** The
  system-user token does not expire; media stays private and is deleted after
  processing, with a one-day lifecycle rule as a safety net.

## Refactor plan

Each phase is one pull request, keeps every test green and keeps the daily Reel
working. Estimates are for focused work.

| Phase | Work | Est. |
|-------|------|------|
| 0. Safety net | Characterization tests: golden-image tests for slides and the Reel overlay, CLI smoke tests, a recorded Steam fixture for a full day. GitHub Actions CI running pytest. | 3 h |
| 1. Tooling | ruff (lint + format), mypy (strict for `domain`/`application`), pre-commit, uv workspace. | 2 h |
| 2. Domain and ports | Move models to `domain/`, add domain errors, write the Protocols. Replace `SystemExit` in the core. No behavior change. | 3 h |
| 3. Use cases | `BuildPost`, `RenderReel`, `PublishPost` in `application/`; the CLI becomes a thin layer (target: no command over 15 lines). | 4 h |
| 4. Adapters and composition root | Move http, images, render, video, beats, music, s3, instagram to `adapters/`; add `bootstrap.py`; topics receive their dependencies. | 4 h |
| 5. Plugin discovery | Entry-point loader in `plugins.py`; delete `core/registry.py`; import-linter contract in CI. | 2 h |
| 6. Split the Steam plugin | Create `packages/autopost-topic-steam` with its own pyproject, tests and `GameRelease` model replacing `Item.meta`. | 4 h |
| 7. Typed configuration | pydantic-settings for `.env`; validated `SteamTopicConfig` with clear error messages for a bad `topic.yaml`. | 2 h |
| 8. Idempotent daily run | SQLite `PostHistory`; `DailyRun` use case that skips a (topic, date) already published; Windows Task Scheduler guide. | 3 h |
| 9. Second network ready | `Publisher` for Instagram behind the port; YouTube Shorts adapter stub with the upload flow documented. | 2 h |
| 10. Docs | "Write your own topic" guide, CONTRIBUTING, updated README and diagrams. | 2 h |

**Total: about 31 hours.**

## Done when

- `autopost_kit` (engine) has no import of `autopost_topic_steam`; CI fails if one appears.
- A new topic can be added in its own package without touching the engine.
- `daily_run` can be run twice for the same day and posts once.
- `domain/` and `application/` pass `mypy --strict`; test coverage of both is above 90%.
- Instagram and S3 can each be replaced by a fake in tests with one line in `bootstrap.py`.
