def match_outcome(home_score: int, away_score: int) -> int:
    if home_score > away_score:
        return 1
    if home_score < away_score:
        return -1
    return 0


def calculate_points(
    pred_home: int,
    pred_away: int,
    fact_home: int,
    fact_away: int,
) -> tuple[int, int, int, int]:
    """Return (points, exact_score, correct_difference, correct_outcome)."""
    if pred_home == fact_home and pred_away == fact_away:
        return 6, 1, 0, 0

    if (pred_home - pred_away) == (fact_home - fact_away):
        return 3, 0, 1, 0

    if match_outcome(pred_home, pred_away) == match_outcome(
        fact_home,
        fact_away,
    ):
        return 2, 0, 0, 1

    return 0, 0, 0, 0
