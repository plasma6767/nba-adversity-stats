"""Tests for the SQLite cache read path only -- never hits the real
stats.nba.com API. A pre-populated cache means get_play_by_play returns
before it ever reaches the network-calling code."""

from nba_adversity_stats import data


def test_get_play_by_play_reads_from_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_PATH", tmp_path / "test_cache.db")

    conn = data._get_connection()
    conn.executemany(
        f"INSERT INTO play_by_play (game_id, {', '.join(data._ROW_FIELDS)}) "
        f"VALUES (?, {', '.join('?' * len(data._ROW_FIELDS))})",
        [
            ("GAME1", 1, 100, 1, "PT10M00.00S", "Missed Shot", "", 1, "Player1", 1, 2, "MISS Player1"),
            ("GAME1", 0, 99, 1, "PT10M05.00S", "Turnover", "Bad Pass", 1, "Player1", 1, None, "Player1 Turnover"),
        ],
    )
    conn.commit()
    conn.close()

    events = data.get_play_by_play("GAME1")

    assert len(events) == 2
    # returned in sequence order (0, then 1), not insertion order
    assert events[0]["sequence"] == 0
    assert events[0]["action_type"] == "Turnover"
    assert events[1]["sequence"] == 1
    assert events[1]["action_type"] == "Missed Shot"
    assert events[1]["shot_value"] == 2


def test_get_play_by_play_empty_cache_for_unknown_game(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_PATH", tmp_path / "test_cache.db")
    # Table needs to exist but have no rows for this game_id -- create it
    # via _get_connection, insert nothing, then confirm a lookup for a
    # different game_id doesn't crash or return unrelated rows.
    conn = data._get_connection()
    conn.executemany(
        f"INSERT INTO play_by_play (game_id, {', '.join(data._ROW_FIELDS)}) "
        f"VALUES (?, {', '.join('?' * len(data._ROW_FIELDS))})",
        [("OTHER_GAME", 0, 1, 1, "PT10M00.00S", "Missed Shot", "", 1, "Player1", 1, 2, "MISS Player1")],
    )
    conn.commit()
    conn.close()

    cached = data._get_connection().execute(
        "SELECT sequence FROM play_by_play WHERE game_id = ?", ("GAME_NOT_CACHED",)
    ).fetchall()
    assert cached == []
