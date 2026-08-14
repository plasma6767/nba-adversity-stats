"""Player lookup and play-by-play data access, with local SQLite caching.

Uses PlayByPlayV3 directly via its raw JSON response rather than nba_api's
get_normalized_dict(), because that helper is built for the older
resultSets-style endpoints and returns nothing useful for V3's
{"game": {"actions": [...]}} shape.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from nba_api.stats.endpoints import playbyplayv3, playergamelog
from nba_api.stats.static import players

CACHE_PATH = Path(__file__).resolve().parent.parent / "cache.db"

# Being polite to stats.nba.com: pause between play-by-play calls so we
# don't hammer it on a cold cache (first-time pull for a new player).
REQUEST_DELAY_SECONDS = 0.6


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS play_by_play (
            game_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            action_number INTEGER,
            period INTEGER,
            clock TEXT,
            action_type TEXT,
            sub_type TEXT,
            person_id INTEGER,
            player_name TEXT,
            team_id INTEGER,
            shot_value INTEGER,
            description TEXT,
            PRIMARY KEY (game_id, sequence)
        )
        """
    )
    return conn


def find_players(name: str) -> list[dict]:
    """All players matching a name search (substring match against the NBA's
    full-name list -- e.g. "curry" matches Stephen, Seth, Dell, and Eddy
    Curry all at once, so callers must handle more than one result rather
    than silently grabbing the first). Active players are sorted first."""
    matches = players.find_players_by_full_name(name)
    return sorted(matches, key=lambda m: not m["is_active"])


def get_season_game_ids(player_id: int, season: str) -> list[str]:
    """Return every game ID a player appeared in for a given season, e.g. '2023-24'."""
    log = playergamelog.PlayerGameLog(player_id=player_id, season=season)
    rows = log.get_normalized_dict()["PlayerGameLog"]
    return [row["Game_ID"] for row in rows]


_ROW_FIELDS = (
    "sequence",
    "action_number",
    "period",
    "clock",
    "action_type",
    "sub_type",
    "person_id",
    "player_name",
    "team_id",
    "shot_value",
    "description",
)


def _row_to_event(row: tuple) -> dict:
    return dict(zip(_ROW_FIELDS, row))


def get_play_by_play(game_id: str) -> list[dict]:
    """Return play-by-play events for a game, using the local cache when possible.

    Events are ordered by their position in the NBA's own action list
    (`sequence`), not by `action_number` -- that field is not unique
    (e.g. a missed shot and the block that caused it can share one).
    """
    conn = _get_connection()
    cached = conn.execute(
        f"SELECT {', '.join(_ROW_FIELDS)} FROM play_by_play "
        "WHERE game_id = ? ORDER BY sequence",
        (game_id,),
    ).fetchall()
    if cached:
        conn.close()
        return [_row_to_event(row) for row in cached]

    pbp = playbyplayv3.PlayByPlayV3(game_id=game_id)
    time.sleep(REQUEST_DELAY_SECONDS)
    raw = json.loads(pbp.nba_response.get_json())
    actions = raw["game"]["actions"]

    events = [
        {
            "sequence": i,
            "action_number": a["actionNumber"],
            "period": a["period"],
            "clock": a["clock"],
            "action_type": a["actionType"],
            "sub_type": a["subType"],
            "person_id": a["personId"] or None,
            "player_name": a["playerName"] or None,
            "team_id": a["teamId"] or None,
            "shot_value": a["shotValue"] or None,
            "description": a["description"],
        }
        for i, a in enumerate(actions)
    ]

    conn.executemany(
        f"INSERT OR REPLACE INTO play_by_play (game_id, {', '.join(_ROW_FIELDS)}) "
        f"VALUES (?, {', '.join('?' * len(_ROW_FIELDS))})",
        [(game_id, *(e[f] for f in _ROW_FIELDS)) for e in events],
    )
    conn.commit()
    conn.close()
    return events
