# Roadmap

Ids in brackets refer to the requirements list (RF = functional, RNF = non-functional).
The architecture refactor is described in detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Milestone 1: Collect ✅

- [x] Core: `Item` model, `Topic` contract, topic registry, YAML config
- [x] Core: polite HTTP client (spacing, retries, user agent) [RNF05]
- [x] Core: timezone-aware "tomorrow" (Steam uses Pacific time) [RF01]
- [x] Steam: find all games released on a given day, stopping early [RF01]
- [x] Steam: skip vague dates ("Coming soon", "Q4 2026") [RF03]
- [x] Steam: full games only, no soundtracks, demos or DLC [RF04]
- [x] Steam: filter adult content by Steam content descriptors [RF05]
- [x] Steam: rank by position in "popular upcoming" [RF04]
- [x] Steam: details for selected games (genres, studio, price, header image, trailer) [RF02]
- [x] Steam: flag games whose date changed since collection [RF19]
- [x] CLI: `collect` and `topics` commands, table and JSON output [RF18]
- [ ] Cache store responses on disk for a few hours, so re-runs are cheap [RNF05]
- [ ] Handle prices for non-US regions and free-to-play labels [RF03]

## Milestone 2: Build the post ✅

- [x] Top 5 by popularity, skipping blocked words and postponed games [RF04, RF19]
- [x] Carousel: cover (1 → 5) and countdown slides (5 → 1), 1080×1350 [RF07, RF08]
- [x] Caption: list, studio credits, "+N more", hashtags; i18n strings [RF09, RNF08]
- [x] `autopost-kit build steam_releases` writes slides, caption and `post.json` [RF14]
- [ ] Prefer screenshots that show gameplay over ones that are mostly text or logos

## Milestone 3: Reel ✅

Format decided: vertical 1080×1920, a cover then #5 → #1, each game over a
stretch of its Steam trailer, cut on the beat of an NCS track.

- [x] Music library: picks an unused track, keeps `used.json`, NCS credit in the caption
- [x] Beat analysis (librosa, optional): tempo, beats, start of the strong part; cached per track
- [x] Scene lengths snapped to whole bars; every cut on a downbeat
- [x] Trailer clips from Steam HLS streams (skips logos at the start); screenshot fallback
- [x] Layout: trailer band over a blurred copy, texts inside Instagram's safe area
- [x] `autopost-kit build ... --reel` and `autopost-kit reel <post folder>`
- [ ] Pick the most dynamic stretch of a trailer (scene-change detection) instead of a fixed offset
- [ ] Vertical-first cover design (today the 4:5 cover is centered)

## Milestone 4: Publish ✅

- [x] Private S3 bucket with pre-signed links; file deleted after processing; 1-day lifecycle rule [RF12]
- [x] Instagram API with Unified Login (non-expiring system user token) [RF11]
- [x] Reel publishing: container → wait → publish, never retried blindly
- [x] Dry run by default; `--yes` to publish; `instagram check` command
- [ ] Carousel publishing (JPEG slides as carousel items)
- [ ] Failure alerts (email or Telegram) [RF17]

## Milestone 5: Architecture refactor (next)

SOLID, ports and adapters, and the Steam topic as its own package. One phase per
pull request; details, target layout and decisions in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). About 31 hours in total.

- [ ] Phase 0: safety net (golden-image tests, CLI smoke tests, CI on GitHub Actions)
- [ ] Phase 1: tooling (ruff, mypy, pre-commit, uv workspace)
- [ ] Phase 2: `domain/` models and errors, `ports/` Protocols; no `SystemExit` in the core
- [ ] Phase 3: use cases in `application/`; thin CLI
- [ ] Phase 4: infrastructure in `adapters/`; composition root in `bootstrap.py`
- [ ] Phase 5: topics discovered through entry points; core no longer imports Steam
- [ ] Phase 6: `packages/autopost-topic-steam` with a typed `GameRelease` model
- [ ] Phase 7: typed, validated configuration (`.env` and `topic.yaml`)
- [ ] Phase 8: SQLite post history and an idempotent `daily_run` [RF06, RF16, RNF06]
- [ ] Phase 9: `Publisher` port ready for YouTube Shorts
- [ ] Phase 10: "write your own topic" guide, CONTRIBUTING, diagrams

## Milestone 6: Run every day

- [ ] Windows Task Scheduler at 00:00 Pacific (04:05 and 05:05 in Brasília, one run publishes) [RF15]
- [ ] Review mode for the first days: build and dry-run automatically, publish by hand [RF13]
- [ ] Docs: how to run your own account with autopost-kit

## Milestone 7: Same content, more networks

One build per day, published everywhere the user chooses. Each network is a
`Publisher` adapter (see Phase 9 of the refactor); the topic does not change.

- [ ] Per-job list of destinations in `autopost.yaml` (`publish_to: [instagram, youtube, threads, facebook]`),
      each with its own mode (`off` / `review` / `auto`)
- [ ] Per-network caption: length limits, hashtags and links adapted
      (e.g. a short title for YouTube, a 500-character post for Threads)
- [ ] Per-network checks before publishing: format, duration and file size
- [ ] **YouTube Shorts**: upload the same vertical video through the YouTube Data API.
      Uploads from an unverified Google API project stay private until the project passes Google's audit.
- [ ] **Threads**: video post with the caption, through the Threads API (its own use case and token in the Meta app)
- [ ] **Facebook Reels**: publishing through the Pages API needs a Facebook Page linked to the account
- [ ] One publishing record per network in the run history, so a failure on one network
      can be retried without posting again on the others
- [ ] Summary after each run: which networks got the post, with links

## Later

- [ ] TikTok, once the other networks are stable
- [ ] AI-written caption variants, with prompts kept inside the topic [RF10]
- [ ] More languages for posts
- [ ] More topics (other stores, other subjects) as separate plugin packages

## Decisions

- **Busy days** (Nov 2, 2026 had 191 eligible games): post only the top 5 by
  popularity; the cover and caption still show the day's total.
- **Reels over carousels**: more reach, and music can be baked in automatically.
- **Runs on the owner's PC**, not in the cloud: the music files stay local and
  the project stays free apart from cents of S3.
