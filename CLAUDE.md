# nba-adversity-stats

A CLI tool that measures how an NBA player shoots in the play right after adversity (a turnover, a missed shot, or a foul they commit on someone else) versus how they normally shoot. The goal, per the project owner, is "the most undeniable data possible" — every design decision below was chosen for defensibility over speed of building, so don't casually simplify things back without understanding why they're built the way they are (see "Conventions" below).

Full design history and rationale lives in `plan.md` at the repo root — read it before making non-trivial changes. This file is the fast-reference version.

## Commands (verified working from a clean install)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"   # installs nba_api, pytest, ruff
pytest                     # 23 tests, no network calls, runs in <1s
ruff check .                # lint
adversity                   # run the CLI (prompts for a player name)
```

Only Python available on this machine is the system Python (3.9.6) — there is no newer interpreter installed. The project targets 3.9 deliberately; don't use syntax that requires 3.10+ without `from __future__ import annotations` at the top of the file (see Gotchas).

`adversity "player name"` also works directly (skips the prompt). `--season "2023-24"` overrides the default season (auto-computed from today's date).

## Architecture

Four files, each with one job, in a strict pipeline:

- **`data.py`** — the only file that talks to the network or disk. Wraps `nba_api` (pulls from stats.nba.com) and a local SQLite cache (`cache.db`, gitignored). Nothing else in the codebase should import `nba_api` directly.
- **`events.py`** — pure logic, zero I/O. Takes a list of play-by-play event dicts (the shape `data.py` produces) and a player ID; returns adversity events and next-shot outcomes. Deliberately has no dependency on `data.py` so it can be tested with fake, hand-built event lists instead of live API calls — that's what `tests/test_events.py` does.
- **`stats.py`** — aggregates `events.py`'s output across a whole season into FG%/3PT% numbers, post-adversity vs. baseline, with sample sizes.
- **`cli.py`** — the only file that prints to the terminal or reads `input()`. Wires the other three together; contains no computation logic of its own.

Keep this separation. If you're tempted to add a `print()` inside `stats.py` or `events.py`, or an `nba_api` import outside `data.py`, that's a sign the change belongs in a different file.

## Conventions (decided deliberately — don't revert without re-reading why)

- **Three adversity types, not more:** `turnover`, `missed_shot`, `foul`. Fouls were originally split into offensive/defensive/flagrant/technical, then merged back into one category after real-season data showed per-subtype sample sizes were too thin to trust (offensive foul n=6, flagrant n=0, technical n=14 for a full season, vs. n=133 for defensive alone). The split version also had a real bug — an exhaustive foul-subtype list silently dropped an unrecognized subtype ("Double Technical"). The merged version doesn't filter on subtype at all, so it can't miss one.
- **"Next shot" means the player's next field goal attempt, not the next touch.** Search forward and skip anything that isn't a shot (turnovers, fouls, free throws, other players' actions, blocks, steals). An earlier "next touch, whatever type" design was tried and rejected — it fragmented adversity instances across too many outcome types and thinned every sample.
- **Free throws are excluded entirely** — not a valid adversity trigger, not a valid "next shot." Mechanically a different act (stationary, no defender); would muddy a stat about decision-making under pressure.
- **Only fouls the player commits count**, never fouls committed against them.
- **Baseline excludes any shot already claimed as someone else's post-adversity next-shot** (not a flat season average) — otherwise the comparison group partly contains the thing being measured. This is "Phase 1" of the baseline design; "Phase 2" (matching by score margin/quarter/opponent) is designed in `plan.md` but not built yet.
- **20 shots is the small-sample cutoff** in the CLI's display — numbers built on fewer are flagged, not hidden.
- **`ruff` line-length is 120, not the 88 default** — deliberately widened after checking real findings; most were descriptive f-strings/comments, not actual code smell.

## Gotchas (all found by testing against real data, not theoretical)

- **Use `PlayByPlayV3`'s raw JSON, not `nba_api`'s `get_normalized_dict()`.** That helper is built for older resultSets-style endpoints and silently returns nothing for V3's `{"game": {"actions": [...]}}` shape. Pull with `pbp.nba_response.get_json()` and `json.loads()` it yourself (see `data.py`).
- **`actionNumber` is not a unique or reliable sort key.** Some plays emit two rows sharing one actionNumber (a missed shot + the block that caused it, a turnover + the steal that caused it). Order and dedupe by `sequence` (our own counter, set to each row's position in the API's response array) instead, or rows get silently lost or misordered.
- **An offensive foul (and at least one observed flagrant) generates a companion `Turnover` row** for the same player/instant, labeled `sub_type == "Offensive Foul Turnover"`. This is NBA bookkeeping, not a separate event — `events.classify_adversity` already excludes it, but if you touch that function, keep the exclusion or a single play double-counts as both a foul and a turnover.
- **Some rows (blocks, steals) have a blank `action_type` entirely** — only identifiable via the free-text `description` field ("Martin BLOCK (1 BLK)"). Not used anywhere currently (blocks/steals aren't tracked, deliberately — see `plan.md`), but if that changes, there's no clean field to key off.
- **Player name search (`data.find_players`) is a plain substring match**, not fuzzy or nickname-aware. "steph curry" won't match "Stephen Curry." Worse, "curry" alone matches 7 different players (Stephen, Seth, Dell, Eddy, Michael, JamesOn Curry, and Carey **Scurry**). Never take `matches[0]` — `cli.py` already handles disambiguation by listing all matches and asking; keep that if you touch name resolution.
- **stats.nba.com is slow and rate-sensitive.** `data.py` sleeps `REQUEST_DELAY_SECONDS` (0.6s) between play-by-play calls. A first-time pull for a new player (up to 82 games) takes a minute or two — this is normal, not a hang.
