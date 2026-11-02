# Roadmap

Ids in brackets refer to the requirements list (RF = functional, RNF = non-functional).

## Milestone 1: Collect (in progress)

- [x] Core: `Item` model, `Topic` contract, topic registry, YAML config
- [x] Core: polite HTTP client (spacing, retries, user agent) [RNF05]
- [x] Core: timezone-aware "tomorrow" (Steam uses Pacific time) [RF01]
- [x] Steam: find all games released on a given day, stopping early [RF01]
- [x] Steam: skip vague dates ("Coming soon", "Q4 2026") [RF03]
- [x] Steam: full games only, no soundtracks, demos or DLC [RF04]
- [x] Steam: filter adult content by Steam content descriptors [RF05]
- [x] Steam: rank by position in "popular upcoming" [RF04]
- [x] Steam: details for selected games (genres, studio, price, header image) [RF02]
- [x] Steam: flag games whose date changed since collection [RF19]
- [x] CLI: `collect` and `topics` commands, table and JSON output [RF18]
- [ ] Cache store responses on disk for a few hours, so re-runs are cheap [RNF05]
- [ ] Handle prices for non-US regions and free-to-play labels [RF03]

## Milestone 2: Build the post

- [ ] Core: `Post` and `Slide` models; carousel limit of 10 slides
- [ ] Steam `select()`: decide what fits when a day has 200+ games (see open question)
- [ ] Core: slide renderer with Pillow and token templates (`{date}`, `{total}`, `{name}`, `{genre}`) [RF07, RF08]
- [ ] Steam templates: cover slide, list slide (10 × `Name — Genre`), capsule highlight slide [RF07]
- [ ] Core: caption templates with tokens and hashtags [RF09]
- [ ] Core: i18n, English first, every text in a locale file [RNF08]
- [ ] Note on every post: dates come from Steam and may change [RF20]
- [ ] `autopost-kit build steam_releases --dry-run` writes slides + caption to `output/` [RF14]

## Milestone 3: Review and history

- [ ] Review flow: generate, then wait for approval before publishing [RF13]
- [ ] SQLite history of collected and published items; no repeats [RF06, RF16]
- [ ] Re-check release dates right before publishing; drop postponed games [RF19]
- [ ] Never publish a half-built post if any step fails [RNF06]

## Milestone 4: Publish

- [ ] Upload slide images to public storage (S3) [RF12]
- [ ] Instagram API with Instagram Login: carousel container → publish [RF11]
- [ ] Token refresh for long-lived tokens
- [ ] Failure alerts (email or Telegram) [RF17]

## Milestone 5: Run every day

- [ ] GitHub Actions schedule at 00:00 Pacific, posting the next day's games [RF15]
- [ ] Handle daylight saving changes in the schedule
- [ ] Docs: how to run your own account with autopost-kit

## Later

- [ ] AI-written caption variants, with prompts kept inside the topic [RF10]
- [ ] More languages for posts
- [ ] More topics (other stores, other subjects) using the same core

## Open questions

- **Busy days.** Some days have 200+ games (Nov 2, 2026: 203 full games). The carousel holds
  at most 8 list slides × 10 names = 80 games. Options: list only the top N by
  popularity and end with "+ X more on Steam", or split into two posts.
