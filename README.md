# autopost-kit

A pluggable engine that turns public data into Instagram carousels.

The **core** knows how to build posts: slides, captions, review, publishing,
scheduling and history. A **topic** is a small plugin that says where the data
comes from, what goes into the post and how the post should look. Adding a new
subject means adding a topic, not touching the core.

The first topic is **`steam_releases`**: every day it lists the games coming out
on Steam *tomorrow*, for the Instagram account
[@tomorrowonsteam](https://www.instagram.com/tomorrowonsteam/).

> Status: early development. Collecting works; slide rendering, review and
> publishing are next. See [ROADMAP.md](ROADMAP.md).

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

Planned carousel for `steam_releases` (up to 10 slides):

1. **Cover**: "Nov 3 on Steam: 20 new games"
2. **Lists**: 10 games per slide, `Name — Genre`
3. **Highlights**: capsule images of the most wanted games fill the remaining slides

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
```

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
timezone, how many days ahead, content filters and request limits.

## Data and content policy

- Data comes from the public Steam store pages and the endpoints the store website
  itself uses. They are not an official API, so the client waits between requests,
  retries gently and identifies itself in the user agent.
- Games marked by Steam with adult sexual content are left out by default.
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
