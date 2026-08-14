# NBA Adversity Stats — Project Plan

## What this is

A command-line tool. You type in an NBA player's name, it tells you how that player *shoots* right after something bad happens to them in a game — a turnover, a missed shot, or a foul they commit on someone else — compared to how they normally shoot. Two numbers: field goal % and 3-point % on the next shot attempt after each adversity type, versus their normal field goal % and 3-point %.

## Why

Goal is to build the most defensible version of this stat possible, not just a fun one. Every design choice below was picked with "would this survive an argument with a skeptical front-office analyst" in mind, over what's fastest to build.

## Definitions

**Adversity events (v1), three types:**
- Turnover
- Missed shot (field goal misses only, not free throws)
- Foul (any sub-type the player commits — offensive, defensive, flagrant, technical, all merged into one category)

Only fouls the player *commits* count — never fouls committed against them. We initially split fouls into offensive/defensive/flagrant/technical, but per-subtype sample sizes checked against a real season were too small to be reliable on their own (offensive foul n=6, flagrant n=0, technical n=14 for one full season, versus a solid n=133 for defensive foul alone) — merged into one "foul" category for v1 instead. That merge also fixed a real bug: the split version required an exhaustive list of foul sub-types, and a real one ("Double Technical," called on both teams after an altercation) wasn't in the list and was silently dropped from adversity detection. The merged version can't miss a sub-type since it doesn't filter on sub-type at all.

Verified against real play-by-play: an offensive foul (and, in at least one case, a flagrant) generates a companion `Turnover` row for bookkeeping purposes (NBA labels it `"Offensive Foul Turnover"`). That companion row must be excluded from turnover-detection, or the same physical play gets double-counted as both a turnover and a foul.

**What we measure = shooting only.** The very next *field goal attempt* (2 or 3 pointer, make or miss) by that player after the adversity event — skipping over anything in between that isn't a shot (turnovers, fouls, free throws, other players' actions). Not the literal next thing that happens, specifically the next shot.

Why not "the literal next touch, whatever it is": we tried that first and it causes a sample-size problem — if a turnover, a foul, a block, or a steal can all independently count as "the next thing," the player's adversity instances get scattered across many different outcome types, leaving too few instances backing any single number (e.g. only 15-30 of 80 turnovers might have "a shot" as the literal next thing). Restricting to "his next shot, however many other things happen first" means nearly every adversity instance eventually contributes a real shooting data point, giving a much bigger and steadier sample. This also means blocks, steals, assists, and rebounds are not tracked in v1 — they were considered and dropped for this reason.

Free throws are excluded both from triggering adversity and from counting as a qualifying "next shot" — free throw shooting is mechanically a different act (stationary, no defender) and would muddy a stat about shot decision-making under pressure.

**Baseline = context-matched comparison, not flat season average.**

Turnovers and fouls don't happen randomly — they cluster against good defenses and in tight games. Comparing post-adversity shooting to a flat season average lets a skeptic say a dip is just "tough defense," not adversity. Instead, compare post-adversity next-shot performance to that same player's shooting in similar game situations (score margin, quarter, opponent) that weren't preceded by an adversity event.

**Build order for the baseline (two phases, not one big jump):**
1. **Phase 1 (build first):** compare post-adversity next-shot FG%/3PT% to the player's *other* shots this season (not situation-matched yet). Simple, fast to build, and lets us prove the pipeline works and sanity-check numbers by hand against real box scores.
2. **Phase 2:** layer in situation-matching (score margin, quarter, opponent) once Phase 1 is validated. This is the version we actually want to report, but it's not worth debugging alongside the core pipeline at the same time.

## Data source

`nba_api` — free Python package pulling from stats.nba.com. Specifically the `PlayByPlayV3` endpoint, read via its raw JSON response rather than the package's built-in parser (that parser is built for an older data format and returns nothing useful for V3). Provides:
- Player name → player ID lookup (no network call needed, it's bundled static data)
- Season game logs for a player (which games they played)
- Full play-by-play per game (every shot, turnover, foul, in order, tagged by player, including shot value so 2s and 3s are distinguishable)

Same underlying data real box scores are built from, so results can be checked by hand.

**Real gotchas found and fixed while building the data layer:**
- System Python here is 3.9 — modern `int | None` type hints need `from __future__ import annotations` at the top of the file, or they crash.
- The API's `actionNumber` field is not a unique or reliable sort key — some plays emit two rows sharing one actionNumber (a missed shot + the block that caused it, a turnover + the steal that caused it). Using it as a cache key silently drops rows. Fixed by keying on each event's actual position in the API's response array instead (`sequence`).
- Some rows (blocks, steals) have a blank `action_type` entirely — the only way to identify them at all is the free-text `description` field. Not used in v1 since blocks/steals aren't tracked, but worth remembering if that changes later.
- `shotValue` (2 or 3) and `shotResult` ("Made"/"Missed") are clean, reliable fields on shot-attempt rows — confirmed against real data, no text-parsing needed for shot classification.

**Caveats:** stats.nba.com is slow and doesn't like being hammered with requests. First pull for a new player (up to 82 games) will take a minute or two; not instant.

## Tech stack

- **Language:** Python — only real ecosystem with the NBA data tooling (`nba_api`, `pbpstats`)
- **Cache/storage:** SQLite (`cache.db`) — a local file, no server. Raw play-by-play gets cached per game after first pull so repeat lookups for a player (or a different player from an already-pulled game) are instant instead of re-hitting stats.nba.com
- **CLI:** typed player name in, formatted stats breakdown out

## Pipeline

1. Resolve player name → player ID (fuzzy match, handles typos/partial names)
2. Pull that player's games for the season — from cache if we have it, from `nba_api` if not
3. Walk each game's play-by-play in order (using a cleaned, de-duplicated version of the event list — see companion-row note above), tag every adversity event (turnover, missed shot, or foul) belonging to that player
4. For each tagged event, find the player's next field goal attempt, whatever else happens first
5. Record whether it was a make or miss, and whether it was a 2 or a 3
6. Aggregate across all games, per adversity type: post-adversity FG% and 3PT% vs. baseline FG%/3PT% (Phase 1: all his other shots; Phase 2: situation-matched shots)
7. Report the percentage-point difference per adversity type, along with sample size, so low-sample numbers are visibly flagged rather than presented as solid

## CLI usage

```
$ adversity
Please enter a player's name to see their adversity stats: luka doncic
```

A name can also be passed directly (`adversity "luka doncic"`), and `--season "2023-24"` overrides the default season. If a name matches more than one player (e.g. "curry"), the CLI lists all matches and asks which one you meant rather than guessing.

Output: for each of the three adversity types, FG% and 3PT% on the next shot after that event, normal FG%/3PT% for comparison, and the sample size behind each number — numbers built on fewer than 20 shots are flagged as a small sample.

## Scope for v1

- One current NBA season
- A handful of players to start, validated by hand against real box scores, before opening it up to any player by name
- The CLI interface itself (name in, stats out) is not limited to those players — the small-scope testing is about what we've pulled and checked, not a hardcoded restriction in the tool

## Open items / risks

- 3PT% specifically could still end up thin for the foul category for some players even after merging (only shots that happen to be 3-pointers count toward that number) — worth watching once we run this on more players
- Phase 2's situation-matching will thin the sample further; may need to be judicious about how many context dimensions we match on
- Rate limiting from stats.nba.com may require deliberate delays between calls on first pull
