"""Aggregate adversity-event outcomes across a season into FG%/3PT% stats."""

from __future__ import annotations

from typing import Callable

from nba_adversity_stats.data import get_play_by_play, get_season_game_ids
from nba_adversity_stats.events import (
    ADVERSITY_TYPES,
    find_adversity_events,
    find_all_shots,
    find_next_shot,
)


def _shot_pool_stats(shots: list[dict]) -> dict:
    n_fg = len(shots)
    fg_made = sum(1 for s in shots if s["made"])
    fg_pct = fg_made / n_fg if n_fg > 0 else None

    threes = [s for s in shots if s["shot_value"] == 3]
    n_3pt = len(threes)
    three_made = sum(1 for s in threes if s["made"])
    three_pct = three_made / n_3pt if n_3pt > 0 else None

    return {
        "n_fg": n_fg,
        "fg_made": fg_made,
        "fg_pct": fg_pct,
        "n_3pt": n_3pt,
        "three_made": three_made,
        "three_pct": three_pct,
    }


def _pct_diff(post: float | None, baseline: float | None) -> float | None:
    if post is None or baseline is None:
        return None
    return post - baseline


def compute_player_adversity_stats(
    player_id: int,
    season: str,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Pull every game a player played in a season and compute their FG%/3PT%
    on the next shot after each adversity type, versus their baseline
    shooting (every other shot that season -- see events.py for why baseline
    excludes any shot that's already someone else's post-adversity
    next-shot).

    If given, on_progress(games_done, games_total) is called after each game
    is processed -- games can take a while to fetch on a first (uncached) run.
    """
    game_ids = get_season_game_ids(player_id, season)

    baseline_shots: list[dict] = []
    per_type_shots: dict[str, list[dict]] = {t: [] for t in ADVERSITY_TYPES}

    for i, game_id in enumerate(game_ids):
        events = get_play_by_play(game_id)
        all_shots = find_all_shots(events, player_id)
        adversity_events = find_adversity_events(events, player_id)

        claimed_sequences = set()
        for adversity in adversity_events:
            shot = find_next_shot(events, player_id, adversity["sequence"])
            if shot is None:
                continue
            per_type_shots[adversity["adversity_type"]].append(shot)
            claimed_sequences.add(shot["sequence"])

        baseline_shots.extend(s for s in all_shots if s["sequence"] not in claimed_sequences)

        if on_progress is not None:
            on_progress(i + 1, len(game_ids))

    baseline = _shot_pool_stats(baseline_shots)

    adversity_stats = {}
    for adversity_type in ADVERSITY_TYPES:
        pool = _shot_pool_stats(per_type_shots[adversity_type])
        pool["fg_pct_diff"] = _pct_diff(pool["fg_pct"], baseline["fg_pct"])
        pool["three_pct_diff"] = _pct_diff(pool["three_pct"], baseline["three_pct"])
        adversity_stats[adversity_type] = pool

    return {
        "player_id": player_id,
        "season": season,
        "games_played": len(game_ids),
        "baseline": baseline,
        "adversity": adversity_stats,
    }
