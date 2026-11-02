# autopost-kit

A pluggable engine that turns public data into Instagram carousels.

The **core** knows how to build posts: slides, captions, review, publishing,
scheduling and history. A **topic** is a small plugin that says where the data
comes from, what goes into the post and how the post should look. Adding a new
subject means adding a topic, not touching the core.

The first topic is **`steam_releases`**: every day it lists the games coming out
on Steam *tomorrow*, for the Instagram account
[@tomorrowonsteam](https://www.instagram.com/tomorrowonsteam/).

> Status: early development. Collecting and building posts work; review,
> history and publishing are next. See [ROADMAP.md](ROADMAP.md).

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

Carousel for `steam_releases` (6 slides, 1080×1350):

1. **Cover**: the day's total ("191 new games") and the top 5, from 1 to 5
2. **Countdown**: one slide per game from #5 to #1, with a Steam screenshot,
   the store header art, genres, studio and a badge (Early Access, Free to Play or price)

The caption lists the 5 games with studio credits, how many more launch that
day and the hashtags. Music is chosen by hand in the Instagram app.

## Requirements

- Python 3.10+
- Internet access to `store.steampowered.com`

## Install

```bash
git clone https://github.com/marciosalsa/autopost-kit.git
cd autopost-kit
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
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
├── core/                     # generic: models, topic contract, http, dates
└── topics/
    └── steam_releases/       # collector, Steam client, parsing, topic.yaml
tests/                        # pytest suite and fixtures
```

## License

[MIT](LICENSE) © 2026 Marcio Salsa

Bundled fonts (Bebas Neue, Inter) are under the SIL Open Font License; see
`src/autopost_kit/assets/fonts/`.
