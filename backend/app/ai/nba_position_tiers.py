"""
NBA position height tiers for amateur pickup comparison.
Maps user position + gender to expected height ranges; NBA data used for playstyle matching.
Games to 15 (pickup) — not 1:1 with NBA 48-min games; stat ratios matter more than raw volume.

NBA avg heights by position (2024): PG 76", SG 77", SF 78", PF 80", C 81"
Female rec ball (amateur): ~6–8" less — PG 68", SG 70", SF 72", PF 74", C 76"
"""
# NBA position avg heights (inches) — for filtering which NBA players to consider
NBA_POS_HEIGHT_MIN = {
    "PG": 70,   # Don't match 5'7" guards to centers
    "SG": 72,
    "SF": 74,
    "PF": 76,
    "C": 78,
}
NBA_POS_HEIGHT_MAX = {
    "PG": 82,
    "SG": 84,
    "SF": 86,
    "PF": 88,
    "C": 92,
}

# User expected height by position+gender (inches) — for physical distance normalization
# Male: NBA-like distribution; Female: rec ball typical
USER_EXPECTED_HEIGHT = {
    "male": {"PG": 74, "SG": 76, "SF": 78, "PF": 79, "C": 80},
    "female": {"PG": 66, "SG": 68, "SF": 70, "PF": 72, "C": 74},
    "other": {"PG": 72, "SG": 74, "SF": 76, "PF": 78, "C": 79},  # Midpoint
}

# NBA position string matching (row["POSITION"] may be "Guard", "Guard-Forward", etc.)
NBA_POS_TO_USER = {
    "PG": ["GUARD", "POINT"],
    "SG": ["GUARD", "SHOOTING"],
    "SF": ["FORWARD", "SMALL"],
    "PF": ["FORWARD", "POWER"],
    "C": ["CENTER", "FORWARD"],
}


def get_user_expected_height(gender: str | None, position: str | None) -> float:
    """Expected height in inches for physical distance normalization."""
    g = (gender or "male").lower()
    if g not in USER_EXPECTED_HEIGHT:
        g = "other"
    pos = (position or "SF").upper()
    return float(USER_EXPECTED_HEIGHT[g].get(pos, 76))


def nba_height_in_range_for_position(nba_height: float, user_position: str | None) -> bool:
    """Return True if NBA player's height is in valid range for user's position."""
    if not user_position:
        return True
    pos = user_position.upper()
    min_h = NBA_POS_HEIGHT_MIN.get(pos, 70)
    max_h = NBA_POS_HEIGHT_MAX.get(pos, 92)
    return min_h <= nba_height <= max_h


def position_match_penalty(nba_pos_str: str, user_position: str | None) -> float:
    """Penalty 0–0.5 when NBA position doesn't align with user position."""
    if not user_position:
        return 0.0
    nba_upper = (nba_pos_str or "").upper()
    keywords = NBA_POS_TO_USER.get(user_position.upper(), [])
    if any(kw in nba_upper for kw in keywords):
        return 0.0
    return 0.4  # Mismatch penalty
