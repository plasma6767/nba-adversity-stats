from nba_adversity_stats.events import (
    classify_adversity,
    find_adversity_events,
    find_all_shots,
    find_next_shot,
)

from conftest import ev


def test_classify_adversity_missed_shot():
    assert classify_adversity(ev(1, "Missed Shot")) == "missed_shot"


def test_classify_adversity_made_shot_is_not_adversity():
    assert classify_adversity(ev(1, "Made Shot")) is None


def test_classify_adversity_turnover():
    assert classify_adversity(ev(1, "Turnover", sub_type="Bad Pass")) == "turnover"


def test_classify_adversity_companion_turnover_excluded():
    # Regression test: an offensive foul's bookkeeping turnover row must
    # NOT count as a separate adversity event, or a single play
    # double-counts as both a foul and a turnover.
    assert classify_adversity(ev(1, "Turnover", sub_type="Offensive Foul Turnover")) is None


def test_classify_adversity_foul_any_subtype():
    # v1: all foul subtypes merge into one "foul" category.
    assert classify_adversity(ev(1, "Foul", sub_type="Shooting")) == "foul"
    assert classify_adversity(ev(1, "Foul", sub_type="Technical")) == "foul"
    assert classify_adversity(ev(1, "Foul", sub_type="Flagrant Type 2")) == "foul"


def test_classify_adversity_irrelevant_action():
    assert classify_adversity(ev(1, "Rebound")) is None


def test_offensive_foul_counts_once_not_twice():
    # Real sequence from Luka Doncic 0022301161: Martin (id 99) commits an
    # offensive charge, which the NBA logs as a Foul row immediately
    # followed by a companion Turnover row for the same player/instant.
    events = [
        ev(405, "Rebound", person_id=2),
        ev(406, "Foul", sub_type="Offensive Charge", person_id=99),
        ev(407, "Turnover", sub_type="Offensive Foul Turnover", person_id=99),
        ev(408, "Violation", person_id=3),
    ]
    results = find_adversity_events(events, player_id=99)
    assert len(results) == 1
    assert results[0]["adversity_type"] == "foul"
    assert results[0]["sequence"] == 406


def test_find_adversity_events_only_matches_target_player():
    events = [
        ev(1, "Turnover", sub_type="Bad Pass", person_id=1),
        ev(2, "Turnover", sub_type="Bad Pass", person_id=2),
        ev(3, "Missed Shot", person_id=1),
    ]
    results = find_adversity_events(events, player_id=1)
    assert [r["sequence"] for r in results] == [1, 3]


def test_find_adversity_events_preserves_order():
    events = [
        ev(5, "Turnover", sub_type="Bad Pass"),
        ev(2, "Missed Shot"),
        ev(8, "Foul", sub_type="Personal"),
    ]
    results = find_adversity_events(events, player_id=1)
    assert [r["sequence"] for r in results] == [5, 2, 8]  # input order, not re-sorted


def test_find_next_shot_skips_non_shot_events():
    events = [
        ev(10, "Turnover", sub_type="Bad Pass", person_id=1),  # the adversity trigger
        ev(11, "Rebound", person_id=2),  # someone else, irrelevant
        ev(12, "Foul", sub_type="Personal", person_id=1),  # not a shot, skip
        ev(13, "Free Throw", person_id=1),  # excluded by design, skip
        ev(14, "Missed Shot", person_id=1, shot_value=3),  # this is the real next shot
    ]
    result = find_next_shot(events, player_id=1, after_sequence=10)
    assert result == {"sequence": 14, "made": False, "shot_value": 3}


def test_find_next_shot_ignores_other_players_shots():
    events = [
        ev(1, "Turnover", sub_type="Bad Pass", person_id=1),
        ev(2, "Made Shot", person_id=2, shot_value=2),  # not the target player
        ev(3, "Made Shot", person_id=1, shot_value=3),
    ]
    result = find_next_shot(events, player_id=1, after_sequence=1)
    assert result["sequence"] == 3
    assert result["made"] is True
    assert result["shot_value"] == 3


def test_find_next_shot_returns_none_when_no_more_shots():
    events = [
        ev(1, "Turnover", sub_type="Bad Pass", person_id=1),
        ev(2, "Substitution", person_id=1),
    ]
    assert find_next_shot(events, player_id=1, after_sequence=1) is None


def test_find_next_shot_ignores_events_before_after_sequence():
    events = [
        ev(1, "Made Shot", person_id=1, shot_value=2),  # before the adversity event, must be ignored
        ev(5, "Turnover", sub_type="Bad Pass", person_id=1),
        ev(9, "Missed Shot", person_id=1, shot_value=2),
    ]
    result = find_next_shot(events, player_id=1, after_sequence=5)
    assert result["sequence"] == 9


def test_find_all_shots():
    events = [
        ev(1, "Made Shot", person_id=1, shot_value=2),
        ev(2, "Missed Shot", person_id=2, shot_value=3),  # other player, excluded
        ev(3, "Missed Shot", person_id=1, shot_value=3),
        ev(4, "Turnover", sub_type="Bad Pass", person_id=1),  # not a shot, excluded
    ]
    shots = find_all_shots(events, player_id=1)
    assert shots == [
        {"sequence": 1, "made": True, "shot_value": 2},
        {"sequence": 3, "made": False, "shot_value": 3},
    ]
