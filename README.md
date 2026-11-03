# autopost-kit

A pluggable engine that turns public data into Instagram Reels and carousels.

The **core** knows how to build posts: slides, captions, review, publishing,
scheduling and history. A **topic** is a small plugin that says where the data
comes from, what goes into the post and how the post should look. Adding a new
subject means adding a topic, not touching the core.

The first topic is **`steam_releases`**: every day it lists the games coming out
on Steam *tomorrow*, for the Instagram account
[@tomorrowonsteam](https://www.instagram.com/tomorrowonsteam/).

> Status: working end to end and posting daily: collect → select → render a
> beat-synced Reel with game trailers → publish through the Instagram API.
> Next: an architecture refactor (ports and adapters, the Steam topic as its own
> package). See [ROADMAP.md](ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## How it works

```
            core (generic)                          topic (steam_releases)
 ┌──────────────────────────────────┐     ┌─────────────────────────────────────┐
 │ pipeline: collect → select →     │ ──▶ │ collect(): tomorrow's games on Steam │
 │ build post → review → publish    │     │ select():  full list + most wanted   │
 │ render · captions · i18n         │ ◀── │ build_post(): cover, lists, capsules │
 │ instagram · storage · history    │     │ topic.yaml: timezone, filters, limits│
 └──────────────────────────────────┘     └─────────────────────────────────────┘
```

Every day the `steam_releases` topic picks the 5 most anticipated games
launching tomorrow and makes:

- **A Reel** (1080×1920, about a minute): a cover with the day's total and the
  top 5, then a countdown from #5 to #1. Each game plays a stretch of its Steam
  trailer over a blurred copy of itself, with rank, name, genres, studio and a
  badge (Early Access, Free to Play or price). Cuts land on the beat of an NCS song.
- **A carousel** (6 slides, 1080×1350) with the same countdown and Steam screenshots.

The caption lists the 5 games with studio credits, how many more launch that
day, the hashtags and the song credit.

### Reels with music

Put songs in `music/` (ignored by git). `autopost-kit reel <post folder>` (or
`build ... --reel`) makes `reel.mp4` with a song that hasn't been used yet, and
writes `reel_caption.txt` with the song credit (from `music/<song>.txt` when
present, otherwise from the file name).

With the optional `music` extra, each song is analysed once (tempo, beats and
where its strong part starts, cached as `<song>.beats.json`) and every scene
lasts a whole number of bars, so cuts land on the beat. Trailers are read from
Steam's streams with ffmpeg; a game without a trailer falls back to a
screenshot. `--slideshow` makes the older slide-based Reel instead.
A song is logged in `music/used.json` only when the Reel is published with
`--yes`; once every song was used, the one used longest ago comes back.
`autopost-kit music` lists the songs and their status. Requires `ffmpeg`.

## Requirements

- Python 3.10+
- Internet access to `store.steampowered.com`
- [ffmpeg](https://ffmpeg.org/) for Reels (Windows: `winget install --id Gyan.FFmpeg -e`)
- To publish: an Instagram professional account connected to a Meta app
  (Instagram API with Unified Login) and a private S3 bucket. See [`.env.example`](.env.example).

## Install

```bash
git clone https://github.com/marciosalsa/autopost-kit.git
cd autopost-kit
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev,music]"   # "music" adds beat-synced cuts (librosa)
```

## Usage

```bash
autopost-kit topics                                  # list topics
autopost-kit collect steam_releases                  # tomorrow (Pacific time)
autopost-kit collect steam_releases --date 2026-11-03 --details 15
autopost-kit collect steam_releases --json > tomorrow.json
autopost-kit -v collect steam_releases               # with progress logs
autopost-kit build steam_releases                    # slides + caption in output/
autopost-kit build steam_releases --date 2026-11-03
```

`build` writes `slide_01.png` … `slide_06.png`, `caption.txt` and `post.json`
to `output/steam_releases/<date>/`. Nothing is published.

Reels and publishing:

```bash
autopost-kit build steam_releases --reel             # post + reel.mp4
autopost-kit reel output/steam_releases/2026-11-04   # Reel for an existing post
autopost-kit music                                    # songs and which ones were used
autopost-kit instagram check                          # token and connected account
autopost-kit publish reel output/steam_releases/2026-11-04/reel.mp4        # dry run
autopost-kit publish reel output/steam_releases/2026-11-04/reel.mp4 --yes  # publish
```

Publishing uploads the video to S3, hands Instagram a pre-signed link that
expires in an hour, waits until Instagram has processed it and deletes the
upload. Without `--yes` it does everything except the final publish.

Example output:

```
Nov 03, 2026 on Steam: 118 games

  1. Example Quest  [popularity #4]
       Action, Adventure, RPG | Example Studio
  2. Another Example  [popularity #17]
       Casual, Indie, Simulation | Another Studio
  ...
```

Settings live in [`topic.yaml`](src/autopost_kit/topics/steam_releases/topic.yaml):
timezone, how many games, blocked title words, colors, hashtags and request
limits. Post texts live in [`locales/en.yaml`](src/autopost_kit/topics/steam_releases/locales/en.yaml).

## Daily run

Your own preferences live in `autopost.yaml` (git-ignored). Start from the example:

```bash
copy autopost.example.yaml autopost.yaml     # Linux/macOS: cp
```

For each job you choose the topic, the time and timezone, how many days ahead,
the format (`reel`, `carousel` or `both`), the publish mode (`off`, `review`
or `auto`) and any topic setting to override (number of games, clip length,
hashtags...).

```bash
autopost-kit run --dry        # what each job would do right now
autopost-kit run              # do whatever is due
autopost-kit run --force      # run now, even if early or already done
autopost-kit schedule         # how to set up the hourly Windows task
```

The system scheduler only calls `autopost-kit run` every hour. The run decides
whether a job is due, and records each finished day in `run.json` next to the
post, so a day is never posted twice and a run missed while the PC slept is
caught up at the next hour.

## Data and content policy

- Data comes from the public Steam store pages and the endpoints the store website
  itself uses. They are not an official API, so the client waits between requests,
  retries gently and identifies itself in the user agent.
- Games marked by Steam with adult sexual content are left out by default, and
  so are games whose title contains a blocked word (abuse, slurs, politics...).
- Every post credits the studio and links to the game's Steam page. Cover art
  belongs to its owners; any studio can ask for its game to be removed.
- Secrets (Instagram token, AWS keys) live only in `.env`, which is git-ignored.
  See [`.env.example`](.env.example).
- No personal data is collected or stored.

## Tests

```bash
pytest
```

Tests use saved fixtures and fake clients, so they never call Steam.

## Project layout

```
src/autopost_kit/
├── cli.py                    # command line
├── core/                     # generic engine: models, topic contract, rendering,
│   │                         # video/beats/music, S3, daily runs
│   └── publishers/           # Instagram
└── topics/
    └── steam_releases/       # collector, Steam client, parsing, selector, layouts
scripts/run_daily.cmd         # called hourly by Windows Task Scheduler
docs/ARCHITECTURE.md          # current design, target design and refactor plan
tests/                        # pytest suite and fixtures (no network needed)
```

## License

[MIT](LICENSE) © 2026 Marcio Salsa

Bundled fonts (Bebas Neue, Inter) are under the SIL Open Font License; see
`src/autopost_kit/assets/fonts/`.
