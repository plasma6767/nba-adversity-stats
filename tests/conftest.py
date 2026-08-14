"""Shared test helpers -- build fake play-by-play rows without hitting the network."""


def ev(sequence, action_type, sub_type="", person_id=1, shot_value=None, description=""):
    """A fake play-by-play row in the same shape data.get_play_by_play returns."""
    return {
        "sequence": sequence,
        "action_number": sequence,
        "period": 1,
        "clock": "PT10M00.00S",
        "action_type": action_type,
        "sub_type": sub_type,
        "person_id": person_id,
        "player_name": f"Player{person_id}",
        "team_id": 1,
        "shot_value": shot_value,
        "description": description,
    }
