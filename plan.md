# NBA Adversity Stats — Project Plan

## What this is

A command-line tool. You type in an NBA player's name, it tells you how that player performs right after something bad happens to them in a game — a turnover, a missed shot, or a foul called on them — compared to how they normally perform. You get an overall number plus a breakdown per adversity type (post-turnover, post-missed-shot, post-foul).

## Why

Goal is to build the most defensible version of this stat possible, not just a fun one. Every design choice below was picked with "would this survive an argument with a skeptical front-office analyst" in mind, over what's fastest to build.

## Definitions

**Adversity events (v1):**
- Turnover
- Missed shot
- Foul called on the player

More types (offensive foul, and-1 given up, technical foul) can be added later. The event list should be config, not hardcoded, so adding one is cheap.

**"Next play" = next individual involvement.** The very next time that player takes a shot, turns it over, or draws a foul — whenever that happens, not a fixed possession count or a rolling average.

Why: it's the closest in time to the adversity event, which makes it the hardest to argue away as "something else caused that." The tradeoff is smaller sample size per player and no guarantee it happens soon (could be after a sub or a quarter break) — accepted for now, revisit if it becomes a real problem once we see real data.

**Baseline = context-matched comparison, not flat season average.**

Turnovers and fouls don't happen randomly — they cluster against good defenses and in tight games. Comparing post-adversity performance to a flat season average lets a skeptic say the dip is just "tough defense," not adversity. Instead, compare post-adversity next-touches to that same player's next-touches in similar game situations (score margin, quarter, opponent) that weren't preceded by an adversity event.

**Build order for the baseline (two phases, not one big jump):**
1. **Phase 1 (build first):** compare post-adversity next-touches to the player's *other* next-touches (not situation-matched yet). Simple, fast to build, and lets us prove the pipeline works and sanity-check numbers by hand against real box scores.
2. **Phase 2:** layer in situation-matching (score margin, quarter, opponent) once Phase 1 is validated. This is the version we actually want to report, but it's not worth debugging alongside the core pipeline at the same time.

## Data source

`nba_api` — free Python package pulling from stats.nba.com. Provides:
- Player name → player ID lookup (no network call needed, it's bundled static data)
- Season game logs for a player (which games they played)
- Full play-by-play per game (every shot, turnover, foul, in order, tagged by player)

Same underlying data real box scores are built from, so results can be checked by hand.

**Caveats:** stats.nba.com is slow and doesn't like being hammered with requests. Play-by-play text parsing has occasional edge cases (jump balls, replay reviews, out-of-bounds calls) that need handling. First pull for a new player (up to 82 games) will take a minute or two; not instant.

## Tech stack

- **Language:** Python — only real ecosystem with the NBA data tooling (`nba_api`, `pbpstats`)
- **Cache/storage:** SQLite (`cache.db`) — a local file, no server. Raw play-by-play gets cached per game after first pull so repeat lookups for a player (or a different player from an already-pulled game) are instant instead of re-hitting stats.nba.com
- **CLI:** typed player name in, formatted stats breakdown out

## Pipeline

1. Resolve player name → player ID (fuzzy match, handles typos/partial names)
2. Pull that player's games for the season — from cache if we have it, from `nba_api` if not
3. Walk each game's play-by-play in order, tag every turnover, missed shot, and foul that belongs to that player
4. For each tagged event, find the player's next individual involvement (shot, turnover, or drawn foul)
5. Record the outcome of that next touch
6. Aggregate across all games: post-adversity next-touch outcomes vs. baseline next-touch outcomes (Phase 1: all other next-touches; Phase 2: situation-matched next-touches)
7. Compute the rate difference per adversity type, along with sample size, so low-sample numbers are visibly flagged rather than presented as solid

## CLI usage (target)

```
adversity "luka doncic"
```

Output: overall adversity number, then a breakdown for turnovers, missed shots, and fouls separately, each with its sample size next to it.

## Scope for v1

- One current NBA season
- A handful of players to start, validated by hand against real box scores, before opening it up to any player by name
- The CLI interface itself (name in, stats out) is not limited to those players — the small-scope testing is about what we've pulled and checked, not a hardcoded restriction in the tool

## Open items / risks

- Sample size per player per adversity type could end up too thin for Phase 2's situation-matching to be meaningful — won't know until we see real numbers
- Play-by-play parsing edge cases from stats.nba.com may need manual handling as they show up
- Rate limiting from stats.nba.com may require deliberate delays between calls on first pull
