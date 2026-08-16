"""Command-line entrypoint: `adversity` prompts for a player and prints their
FG%/3PT% after each adversity type, versus their normal shooting."""

from __future__ import annotations

import argparse
import sys

from nba_adversity_stats.data import find_players, get_career_seasons
from nba_adversity_stats.events import ADVERSITY_TYPES
from nba_adversity_stats.stats import compute_player_adversity_stats

SMALL_SAMPLE_THRESHOLD = 20

# A career pull means one play-by-play fetch per game across every season --
# for a long career that's a real wait on a first (uncached) run, so we warn
# above this many seasons rather than let it look hung.
LONG_CAREER_WARNING_SEASONS = 5

ADVERSITY_LABELS = {
    "turnover": "a turnover",
    "missed_shot": "a missed shot",
    "foul": "a foul",
}


def _prompt_for_name() -> str:
    return input("Please enter a player's name to see their adversity stats: ").strip()


def _prompt_for_scope() -> str:
    """Ask whether to pull the player's whole career or a single season.
    Returns "career" or "season"."""
    print("View adversity stats for:")
    print("  1. Their whole career")
    print("  2. One season")
    while True:
        choice = input("Which one? [1-2]: ").strip()
        if choice == "1":
            return "career"
        if choice == "2":
            return "season"
        print("Not a valid choice, try again.")


def _prompt_for_season_choice(seasons: list[str]) -> str:
    """Show every season the player has real data for and let the user pick
    one by number, rather than typing a season string freehand -- avoids
    typos landing on a season that doesn't exist."""
    print("Which season?")
    for i, season in enumerate(seasons, start=1):
        print(f"  {i}. {season}")
    while True:
        choice = input(f"Pick a season [1-{len(seasons)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(seasons):
            return seasons[int(choice) - 1]
        print("Not a valid choice, try again.")


def _disambiguate(matches: list[dict]) -> dict:
    print("Multiple players matched:")
    for i, m in enumerate(matches, start=1):
        status = "active" if m["is_active"] else "retired"
        print(f"  {i}. {m['full_name']} ({status})")
    while True:
        choice = input(f"Which one did you mean? [1-{len(matches)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(matches):
            return matches[int(choice) - 1]
        print("Not a valid choice, try again.")


def _fmt_pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def _fmt_diff(value: float | None) -> str:
    if value is None:
        return ""
    sign = "+" if value >= 0 else ""
    return f" ({sign}{value * 100:.1f})"


def _fmt_n(n: int) -> str:
    flag = "  (small sample)" if n < SMALL_SAMPLE_THRESHOLD else ""
    return f"n={n}{flag}"


def _fmt_seasons_header(seasons: list[str]) -> str:
    if len(seasons) == 1:
        return f"{seasons[0]} season"
    return f"career ({seasons[0]} – {seasons[-1]}, {len(seasons)} seasons)"


def _print_report(name: str, seasons: list[str], result: dict) -> None:
    baseline = result["baseline"]
    print(f"\n{name} — {_fmt_seasons_header(seasons)} ({result['games_played']} games)\n")
    print(
        f"Normal shooting: {_fmt_pct(baseline['fg_pct'])} FG ({_fmt_n(baseline['n_fg'])}), "
        f"{_fmt_pct(baseline['three_pct'])} 3PT ({_fmt_n(baseline['n_3pt'])})\n"
    )

    for adversity_type in ADVERSITY_TYPES:
        stat = result["adversity"][adversity_type]
        label = ADVERSITY_LABELS.get(adversity_type, adversity_type)
        print(f"After {label}:")
        print(f"  FG%:  {_fmt_pct(stat['fg_pct'])}{_fmt_diff(stat['fg_pct_diff'])}  [{_fmt_n(stat['n_fg'])}]")
        print(f"  3PT%: {_fmt_pct(stat['three_pct'])}{_fmt_diff(stat['three_pct_diff'])}  [{_fmt_n(stat['n_3pt'])}]")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="adversity",
        description="Show an NBA player's shooting % right after adversity events.",
    )
    parser.add_argument("player_name", nargs="?", default=None, help="Player name, e.g. \"steph curry\"")
    args = parser.parse_args()

    name = args.player_name or _prompt_for_name()
    if not name:
        print("No player name given.")
        sys.exit(1)

    matches = find_players(name)
    if not matches:
        print(f'No player found matching "{name}". Check the spelling and try again.')
        sys.exit(1)
    match = matches[0] if len(matches) == 1 else _disambiguate(matches)

    seasons_played = get_career_seasons(match["id"])
    if not seasons_played:
        print(f"No season data found for {match['full_name']}.")
        sys.exit(1)

    scope = _prompt_for_scope()
    seasons = seasons_played if scope == "career" else [_prompt_for_season_choice(seasons_played)]

    print(f"Fetching {match['full_name']}'s {_fmt_seasons_header(seasons)}...")
    if len(seasons) > LONG_CAREER_WARNING_SEASONS:
        print(f"That's {len(seasons)} seasons of play-by-play on a first (uncached) pull -- this can take a while.")

    def on_progress(done: int, total: int) -> None:
        print(f"\r  {done}/{total} games processed", end="", flush=True)

    result = compute_player_adversity_stats(match["id"], seasons, on_progress=on_progress)
    print()

    if result["games_played"] == 0:
        print(f"No games found for {match['full_name']} across the selected {_fmt_seasons_header(seasons)}.")
        sys.exit(1)

    _print_report(match["full_name"], seasons, result)


if __name__ == "__main__":
    main()
