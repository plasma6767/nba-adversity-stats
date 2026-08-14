"""Adversity event detection and next-shot outcome logic."""

from __future__ import annotations

MADE_SHOT = "Made Shot"
MISSED_SHOT = "Missed Shot"
TURNOVER = "Turnover"
FOUL = "Foul"

OFFENSIVE_FOUL_SUBTYPES = {"Offensive", "Offensive Charge"}
DEFENSIVE_FOUL_SUBTYPES = {
    "Shooting",
    "Personal",
    "Personal Take",
    "Transition Take",
    "Loose Ball",
    "Away From Play",
    "Defense 3 Second",
}
FLAGRANT_FOUL_SUBTYPES = {"Flagrant Type 1", "Flagrant Type 2"}
TECHNICAL_FOUL_SUBTYPE = "Technical"

# A Turnover row with this sub_type is the NBA's bookkeeping companion to
# a Foul row for the same player/instant (verified against real data:
# every Offensive/Offensive Charge/Flagrant foul that costs the offense
# possession pairs 1:1 with a row carrying this exact label). It is not
# a separately-committed turnover, and must be excluded or the same
# physical play double-counts as two adversity events.
COMPANION_TURNOVER_SUBTYPE = "Offensive Foul Turnover"

ADVERSITY_TYPES = (
    "turnover",
    "missed_shot",
    "offensive_foul",
    "defensive_foul",
    "flagrant_foul",
    "technical_foul",
)


def classify_foul(sub_type: str) -> str | None:
    if sub_type in OFFENSIVE_FOUL_SUBTYPES:
        return "offensive_foul"
    if sub_type in DEFENSIVE_FOUL_SUBTYPES:
        return "defensive_foul"
    if sub_type in FLAGRANT_FOUL_SUBTYPES:
        return "flagrant_foul"
    if sub_type == TECHNICAL_FOUL_SUBTYPE:
        return "technical_foul"
    return None


def classify_adversity(event: dict) -> str | None:
    """Adversity category for a raw play-by-play row, or None if it isn't one."""
    if event["action_type"] == TURNOVER:
        if event["sub_type"] == COMPANION_TURNOVER_SUBTYPE:
            return None  # bookkeeping companion to a foul, not its own event
        return "turnover"
    if event["action_type"] == MISSED_SHOT:
        return "missed_shot"
    if event["action_type"] == FOUL:
        return classify_foul(event["sub_type"])
    return None


def find_adversity_events(events: list[dict], player_id: int) -> list[dict]:
    """Every adversity-triggering action by this player in a game, in order.

    Each result: {"sequence": ..., "adversity_type": ..., "event": <the row>}
    """
    results = []
    for event in events:
        if event["person_id"] != player_id:
            continue
        category = classify_adversity(event)
        if category is not None:
            results.append(
                {
                    "sequence": event["sequence"],
                    "adversity_type": category,
                    "event": event,
                }
            )
    return results


def find_next_shot(events: list[dict], player_id: int, after_sequence: int) -> dict | None:
    """The player's next field goal attempt after `after_sequence`, skipping
    over anything in between that isn't a shot (turnovers, fouls, free
    throws, other players' actions). Returns None if the player never
    attempts another shot in this game after that point.

    Each result: {"sequence": ..., "made": bool, "shot_value": 2 or 3}
    """
    for event in events:
        if event["sequence"] <= after_sequence:
            continue
        if event["person_id"] != player_id:
            continue
        if event["action_type"] not in (MADE_SHOT, MISSED_SHOT):
            continue
        return {
            "sequence": event["sequence"],
            "made": event["action_type"] == MADE_SHOT,
            "shot_value": event["shot_value"],
        }
    return None
