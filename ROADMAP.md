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

## Milestone 2: Build the post (in progress)

Format decided: a cover listing the top 5 (1 → 5), then one slide per game
counting down 5 → 1. 1080×1350 slides, fixed channel frame. Music is added by
hand in the Instagram app during review.

- [x] Core: `Post` and `Slide` models; carousel limit of 10 slides
- [x] Core: drawing primitives (fonts, text fitting, cover crop, gradients, pills) [RF08]
- [x] Core: cached image downloads
- [x] Core: i18n, English first, every text in a locale file with `{tokens}` [RNF08]
- [x] Core: generic `build` pipeline and `save_post` to `output/<topic>/<date>/` [RF14]
- [x] Steam `select()`: top 5 by popularity, skipping blocked words and postponed games [RF04, RF19]
- [x] Steam: genres cleanup ("Indie" only when alone) and badges (Early Access, Free to Play, price)
- [x] Steam templates: cover and countdown game slides [RF07]
- [x] Steam caption: list, studio credits, "+N more", hashtags [RF09]
- [x] CLI: `autopost-kit build steam_releases`
- [ ] Fallback when a game has no screenshot (header art enlarged, blurred background)
- [ ] Prefer screenshots that show gameplay over ones that are mostly text or logos
- [ ] Visual regression test: compare rendered slides to approved reference images

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

- [ ] Reel version of each post: slides as a ~15 s video with an NCS track baked in,
      credit added to the caption (ffmpeg). Check NCS terms for automated use first.
- [ ] Short trailer clips from Steam (HLS) as video slides or Reels
- [ ] AI-written caption variants, with prompts kept inside the topic [RF10]
- [ ] More languages for posts
- [ ] More topics (other stores, other subjects) using the same core

## Decisions

- **Busy days** (Nov 2, 2026 had 191 eligible games): post only the top 5 by
  popularity; the cover and caption still show the day's total.
