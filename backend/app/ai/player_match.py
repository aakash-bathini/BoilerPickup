"""
ML-based player matching for Boiler Pickup.

1. find_matches: Similar players (skill, height, position) — for 1v1 or similar-level games.
2. find_complementary_teammates: Players who complement your skills — for teaming up.
   - Scorer + rebounder, playmaker + finisher, etc.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import User, Block, PlayerGameStats


def _parse_height(height_str: str | None) -> float:
    """Parse height string to inches. Returns 70 if unparseable."""
    if not height_str or not height_str.strip():
        return 70.0
    s = height_str.strip().replace('"', "'").replace("-", "'")
    parts = s.split("'")
    try:
        feet = int(parts[0].strip()) if parts else 0
        inch = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else 0
        return max(60, min(96, feet * 12 + inch))
    except (ValueError, IndexError):
        return 70.0


def _position_embedding(pos: str | None) -> float:
    m = {"PG": 0, "SG": 1, "SF": 2, "PF": 3, "C": 4}
    return float(m.get(pos or "SF", 2))


def _user_features(u: User) -> tuple[float, float, float, float]:
    """(skill_norm, height_norm, position_norm, games_norm)."""
    skill_norm = (u.ai_skill_rating - 1) / 9.0
    height_in = _parse_height(u.height)
    height_norm = (height_in - 60) / 36.0
    pos_norm = _position_embedding(u.preferred_position) / 4.0
    total_games = u.games_played + u.challenge_wins + u.challenge_losses
    games_norm = min(1.0, total_games / 30.0)
    return (skill_norm, height_norm, pos_norm, games_norm)


def _distance(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    weights: tuple[float, float, float, float],
) -> float:
    return sum(w * (x - y) ** 2 for w, x, y in zip(weights, a, b)) ** 0.5


def _get_career_stats(db: Session, user_id: int) -> dict:
    """Aggregate career stats for a user. Returns ppg, rpg, apg, spg, bpg, topg, fg_pct."""
    rows = (
        db.query(
            func.avg(PlayerGameStats.pts).label("ppg"),
            func.avg(PlayerGameStats.reb).label("rpg"),
            func.avg(PlayerGameStats.ast).label("apg"),
            func.avg(PlayerGameStats.stl).label("spg"),
            func.avg(PlayerGameStats.blk).label("bpg"),
            func.avg(PlayerGameStats.tov).label("topg"),
            func.sum(PlayerGameStats.fgm).label("fgm"),
            func.sum(PlayerGameStats.fga).label("fga"),
        )
        .filter(PlayerGameStats.user_id == user_id)
        .first()
    )
    if not rows or (rows.fga or 0) == 0:
        return {"ppg": 0, "rpg": 0, "apg": 0, "spg": 0, "bpg": 0, "topg": 0, "fg_pct": 0.5}
    fg_pct = (rows.fgm or 0) / (rows.fga or 1)
    return {
        "ppg": float(rows.ppg or 0),
        "rpg": float(rows.rpg or 0),
        "apg": float(rows.apg or 0),
        "spg": float(rows.spg or 0),
        "bpg": float(rows.bpg or 0),
        "topg": float(rows.topg or 0),
        "fg_pct": fg_pct,
    }


def find_matches(
    db: Session,
    user_id: int,
    limit: int = 10,
    skill_tolerance: float = 1.5,
    exclude_blocked: bool = True,
) -> list[User]:
    """
    Find players most similar to the given user.
    Skill, height, position, experience.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_disabled:
        return []

    blocked = set()
    if exclude_blocked:
        blocks = db.query(Block).filter(
            (Block.blocker_id == user_id) | (Block.blocked_id == user_id)
        ).all()
        for b in blocks:
            blocked.add(b.blocker_id)
            blocked.add(b.blocked_id)

    user_feat = _user_features(user)
    weights = (3.0, 1.0, 0.5, 0.3)

    query = db.query(User).filter(User.is_disabled == False, User.id != user_id)
    if blocked:
        query = query.filter(~User.id.in_(list(blocked)))
    candidates = query.all()

    scored: list[tuple[float, User]] = []
    for c in candidates:
        if skill_tolerance > 0 and abs(c.ai_skill_rating - user.ai_skill_rating) > skill_tolerance:
            continue
        feat = _user_features(c)
        d = _distance(user_feat, feat, weights)
        scored.append((d, c))

    scored.sort(key=lambda x: x[0])
    return [u for _, u in scored[:limit]]


def find_complementary_teammates(
    db: Session,
    user_id: int,
    limit: int = 5,
    skill_tolerance: float = 1.5,
    exclude_blocked: bool = True,
) -> list[User]:
    """
    Find players who COMPLEMENT the user's skills for teaming up.
    - If user is scorer (high PPG): prefer rebounders, playmakers.
    - If user is playmaker (high APG): prefer scorers, finishers.
    - If user is big (high RPG/BPG): prefer guards, shooters.
    - Similar skill level, different stat profile.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.is_disabled:
        return []

    blocked = set()
    if exclude_blocked:
        blocks = db.query(Block).filter(
            (Block.blocker_id == user_id) | (Block.blocked_id == user_id)
        ).all()
        for b in blocks:
            blocked.add(b.blocker_id)
            blocked.add(b.blocked_id)

    my_stats = _get_career_stats(db, user_id)
    my_pos = user.preferred_position or "SF"

    query = db.query(User).filter(User.is_disabled == False, User.id != user_id)
    if blocked:
        query = query.filter(~User.id.in_(list(blocked)))
    candidates = query.all()

    scored: list[tuple[float, User]] = []
    for c in candidates:
        if abs(c.ai_skill_rating - user.ai_skill_rating) > skill_tolerance:
            continue
        their_stats = _get_career_stats(db, c.id)

        # Complement score: reward stats they have that we lack
        comp = 0.0
        # If I'm low on rebounds, value their rebounds
        if my_stats["rpg"] < 3 and their_stats["rpg"] > 4:
            comp += 2.0 * min(their_stats["rpg"] / 6, 1.5)
        # If I'm low on assists, value their playmaking
        if my_stats["apg"] < 1.5 and their_stats["apg"] > 2.5:
            comp += 2.0 * min(their_stats["apg"] / 4, 1.5)
        # If I'm low on scoring, value their scoring
        if my_stats["ppg"] < 4 and their_stats["ppg"] > 6:
            comp += 1.5 * min(their_stats["ppg"] / 10, 1.2)
        # If I'm a guard (PG/SG), value bigs (PF/C) for rebounds/blocks
        if my_pos in ("PG", "SG") and c.preferred_position in ("PF", "C"):
            comp += 1.5 * (their_stats["rpg"] / 5 + their_stats["bpg"] / 1.5)
        # If I'm a big (PF/C), value guards for assists/steals
        if my_pos in ("PF", "C") and c.preferred_position in ("PG", "SG"):
            comp += 1.5 * (their_stats["apg"] / 3 + their_stats["spg"] / 1.5)
        # Position diversity: different position = more complement
        if c.preferred_position and c.preferred_position != my_pos:
            comp += 0.8

        # Slight penalty for too similar stat profile
        stat_sim = (
            abs(my_stats["ppg"] - their_stats["ppg"]) / 10
            + abs(my_stats["rpg"] - their_stats["rpg"]) / 5
            + abs(my_stats["apg"] - their_stats["apg"]) / 3
        )
        comp += stat_sim * 0.5

        scored.append((-comp, c))  # Negative so higher comp sorts first

    scored.sort(key=lambda x: x[0])
    return [u for _, u in scored[:limit]]
