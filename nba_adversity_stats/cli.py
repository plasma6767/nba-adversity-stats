"""Command-line entrypoint: `adversity` prompts for a player and prints their
FG%/3PT% after each adversity type, versus their normal shooting."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from nba_adversity_stats.data import find_players
from nba_adversity_stats.events import ADVERSITY_TYPES
from nba_adversity_stats.stats import compute_player_adversity_stats

SMALL_SAMPLE_THRESHOLD = 20

ADVERSITY_LABELS = {
    "turnover": "a turnover",
    "missed_shot": "a missed shot",
    "foul": "a foul",
}


def _default_season() -> str:
    """Most recently relevant NBA season as of today: the season currently
    underway if we're Oct-Dec (just started) or Jan-Sep (in progress or just
    finished), otherwise last season."""
    today = date.today()
    start_year = today.year if today.month >= 10 else today.year - 1
    return f"{start_year}-{str(start_year + 1)[2:]}"


def _prompt_for_name() -> str:
    return input("Please enter a player's name to see their adversity stats: ").strip()


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


def _print_report(name: str, season: str, result: dict) -> None:
    baseline = result["baseline"]
    print(f"\n{name} — {season} season ({result['games_played']} games)\n")
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
    parser.add_argument("--season", default=None, help='e.g. "2024-25" (defaults to the current/most recent season)')
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

    season = args.season or _default_season()
    print(f"Fetching {match['full_name']}'s {season} season, this may take a minute the first time...")

    def on_progress(done: int, total: int) -> None:
        print(f"\r  {done}/{total} games processed", end="", flush=True)

    result = compute_player_adversity_stats(match["id"], season, on_progress=on_progress)
    print()

    if result["games_played"] == 0:
        print(f"No games found for {match['full_name']} in {season}.")
        sys.exit(1)

    _print_report(match["full_name"], season, result)


if __name__ == "__main__":
    main()
