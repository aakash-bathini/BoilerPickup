"""
Skill Rating System — position-aware, all stats, game-type normalized.

Pickup basketball: game to 15. 5v5 harder to score than 3v3/2v2.
- 5v5: ~3 PPG, 2 RPG, 1 APG, 0.5 SPG, 0.3 BPG, 1 TOPG (avg player)
- 3v3: ~5 PPG, 3 RPG, 1.5 APG, 0.8 SPG, 0.5 BPG, 1.2 TOPG
- 2v2: ~7.5 PPG, 4 RPG, 2 APG, 1 SPG, 0.6 BPG, 1.5 TOPG

Position weights (what matters for each role):
- PG: assists, steals, low TOV (playmaking)
- SG/SF: scoring, 3P%, efficiency
- PF/C: rebounds, blocks, FG% (paint presence)
"""
import math
from sqlalchemy.orm import Session

from app.models import Game, GameParticipant, PlayerGameStats, SkillHistory, User

# Per-game-type baselines for "average" 5.0 skill (pickup game to 15)
_GAME_BASELINES = {
    "5v5": {"ppg": 3.0, "rpg": 2.0, "apg": 1.0, "spg": 0.5, "bpg": 0.3, "topg": 1.0, "scale": 1.0},
    "3v3": {"ppg": 5.0, "rpg": 3.0, "apg": 1.5, "spg": 0.8, "bpg": 0.5, "topg": 1.2, "scale": 1.5},
    "2v2": {"ppg": 7.5, "rpg": 4.0, "apg": 2.0, "spg": 1.0, "bpg": 0.6, "topg": 1.5, "scale": 2.0},
}

# Game-type reliability: 5v5 most representative (full squad), 2v2 more variance
_GAME_TYPE_WEIGHT = {"5v5": 1.0, "3v3": 0.95, "2v2": 0.9}

# Position importance: higher = stat matters more for that position
_POSITION_WEIGHTS = {
    "PG": {"ppg": 0.8, "rpg": 0.4, "apg": 1.8, "spg": 1.2, "bpg": 0.2, "topg": -1.2, "fg_pct": 0.6},
    "SG": {"ppg": 1.4, "rpg": 0.5, "apg": 0.9, "spg": 1.0, "bpg": 0.3, "topg": -0.8, "fg_pct": 1.2},
    "SF": {"ppg": 1.2, "rpg": 1.0, "apg": 0.8, "spg": 1.0, "bpg": 0.5, "topg": -0.7, "fg_pct": 1.0},
    "PF": {"ppg": 1.0, "rpg": 1.5, "apg": 0.6, "spg": 0.6, "bpg": 1.2, "topg": -0.6, "fg_pct": 1.0},
    "C": {"ppg": 0.9, "rpg": 1.8, "apg": 0.4, "spg": 0.4, "bpg": 1.5, "topg": -0.5, "fg_pct": 1.1},
}
_DEFAULT_WEIGHTS = {"ppg": 1.0, "rpg": 1.0, "apg": 1.0, "spg": 1.0, "bpg": 1.0, "topg": -1.0, "fg_pct": 1.0}


def get_learning_rate(total_games_before: int) -> float:
    """
    K-factor decay. Each new game matters less as history grows.
    lr = K0 / sqrt(N + 1). Reduced for first few games to avoid overreacting to initial/lying self-report.
    First game: ~25% impact. After 10 games: ~40%. After 25 games: ~8%.
    """
    K0 = 0.5
    lr = K0 / math.sqrt(total_games_before + 1)
    if total_games_before < 3:
        lr = min(lr, 0.25)  # Cap first few games — don't overreact to one win/loss
    return lr


def get_alpha(total_games_before: int) -> float:
    """Prior weight from learning rate. alpha = 1 - lr (weight on old rating)."""
    lr = get_learning_rate(total_games_before)
    return min(max(1.0 - lr, 0.1), 0.95)


def compute_confidence(total_games: int, rating_history: list[float] | None = None) -> float:
    """Bayesian-inspired confidence. Penalty for high variance."""
    base = 1.0 - math.exp(-total_games / 6.0)
    if rating_history and len(rating_history) >= 3:
        mean_r = sum(rating_history) / len(rating_history)
        variance = sum((r - mean_r) ** 2 for r in rating_history) / len(rating_history)
        std = math.sqrt(variance)
        consistency_penalty = min(0.3, std * 0.1)
        base = max(0.05, base - consistency_penalty)
    return round(base, 4)


def _get_position_weights(pos: str | None) -> dict:
    return _POSITION_WEIGHTS.get(pos or "SF", _DEFAULT_WEIGHTS)


def compute_game_performance_rating(
    stats: PlayerGameStats,
    game: Game,
    won: bool,
    score_margin: int,
    avg_opponent_rating: float,
    preferred_position: str | None = None,
) -> float:
    """
    Position-aware, all stats, game-type normalized.
    Uses Hollinger-style efficiency + position-weighted stat contributions.
    """
    base = _GAME_BASELINES.get(game.game_type, _GAME_BASELINES["5v5"])
    weights = _get_position_weights(preferred_position)

    pts, reb, ast = stats.pts, stats.reb, stats.ast
    stl, blk, tov = stats.stl, stats.blk, stats.tov
    fgm, fga = stats.fgm, stats.fga
    three_pm, ftm, fta = stats.three_pm, stats.ftm, stats.fta

    # Normalize each stat by game-type baseline (ratio to average)
    ppg_ratio = pts / max(base["ppg"], 0.5)
    rpg_ratio = reb / max(base["rpg"], 0.5)
    apg_ratio = ast / max(base["apg"], 0.3)
    spg_ratio = stl / max(base["spg"], 0.2)
    bpg_ratio = blk / max(base["bpg"], 0.1)
    topg_ratio = tov / max(base["topg"], 0.5)
    # Lower TOV is better: invert
    tov_score = 1.0 / max(topg_ratio, 0.3) if tov > 0 else 1.5

    # FG% (Laplace smooth)
    fg_pct = fgm / (fga + 1) if fga > 0 else 0.5
    fg_bonus = math.tanh((fg_pct - 0.42) * 8)

    # TS% for efficiency
    ts_attempts = 2.0 * (fga + 0.44 * fta + 1)
    ts_pct = pts / ts_attempts if ts_attempts > 0 else 0.5
    eff_bonus = math.tanh((ts_pct - 0.52) * 6)

    # AST:TOV (playmaking)
    ast_tov = ast / max(tov, 1)
    ast_bonus = math.tanh((ast_tov - 1.2) * 0.4)

    # Position-weighted stat contribution (normalized)
    w = weights
    raw = (
        w["ppg"] * ppg_ratio * 1.2
        + w["rpg"] * rpg_ratio * 0.6
        + w["apg"] * apg_ratio * 0.8
        + w["spg"] * spg_ratio * 0.5
        + w["bpg"] * bpg_ratio * 0.4
        + w["topg"] * tov_score * 0.3
        + w["fg_pct"] * fg_bonus * 0.5
    )
    raw += eff_bonus * 1.0 + ast_bonus * 0.8

    # Scale by game type
    raw *= base["scale"] / 1.5

    # Score margin
    margin_norm = min(abs(score_margin) / 15.0, 1.0)
    margin_factor = 1.0 + (0.25 if won else -0.25) * margin_norm
    raw *= margin_factor

    # Opponent strength
    opp_factor = 1.0 + (avg_opponent_rating - 5.0) * 0.04
    raw *= opp_factor

    # Sigmoid to 1-10
    normalized = 1.0 + 9.0 / (1.0 + math.exp(-(raw - 5.0) / 2.5))
    win_val = 7.5 if won else 3.5
    blended = 0.65 * normalized + 0.35 * win_val

    return round(min(max(blended, 1.0), 10.0), 2)


def detect_sandbagging(user: User, recent_ratings: list[float]) -> bool:
    """Z-score based sandbagging detection."""
    if user.games_played < 5 or len(recent_ratings) < 3:
        return False
    win_rate = user.wins / max(user.games_played, 1)
    if win_rate < 0.65:
        return False
    mean_perf = sum(recent_ratings) / len(recent_ratings)
    diff = mean_perf - user.ai_skill_rating
    if len(recent_ratings) >= 3:
        variance = sum((r - mean_perf) ** 2 for r in recent_ratings) / len(recent_ratings)
        std = max(math.sqrt(variance), 0.3)
        return diff / std > 1.5
    return diff > 1.0


def update_ratings_after_game(
    db: Session,
    game: Game,
    participants: list[GameParticipant],
):
    """Update all participants' skill ratings after a completed game."""
    winning_team = "A" if (game.team_a_score or 0) > (game.team_b_score or 0) else "B"
    score_margin = abs((game.team_a_score or 0) - (game.team_b_score or 0))

    all_ratings = [p.user.ai_skill_rating for p in participants if p.user]
    avg_rating = sum(all_ratings) / len(all_ratings) if all_ratings else 5.0

    for p in participants:
        user = p.user
        if not user:
            continue

        history = (
            db.query(SkillHistory)
            .filter(SkillHistory.user_id == user.id)
            .order_by(SkillHistory.timestamp.desc())
            .limit(10)
            .all()
        )
        rating_hist = [h.new_rating for h in history]

        stat = (
            db.query(PlayerGameStats)
            .filter(
                PlayerGameStats.game_id == game.id,
                PlayerGameStats.user_id == user.id,
            )
            .first()
        )

        opponent_ratings = [
            pp.user.ai_skill_rating for pp in participants
            if pp.user and pp.team != p.team
        ]
        avg_opp = sum(opponent_ratings) / len(opponent_ratings) if opponent_ratings else 5.0

        # First game: discard self-report — use opponent avg as prior (self-report only for matching)
        total_before = user.games_played + user.challenge_wins + user.challenge_losses - 1
        total_before = max(0, total_before)
        old_rating = avg_opp if total_before == 0 else user.ai_skill_rating

        won = p.team == winning_team

        if stat:
            game_rating = compute_game_performance_rating(
                stat, game, won, score_margin, avg_opp, user.preferred_position
            )
        else:
            expected_win = 1.0 / (1.0 + 10.0 ** ((avg_opp - old_rating) / 4.0))
            if won:
                game_rating = old_rating + 1.5 * (1.0 - expected_win)
            else:
                game_rating = old_rating - 1.5 * expected_win
            game_rating = min(max(game_rating, 1.0), 10.0)

        alpha = get_alpha(total_before)
        perf_history = rating_hist[:5]
        if detect_sandbagging(user, perf_history) and game_rating > old_rating:
            alpha = max(alpha - 0.25, 0.1)

        # Game-type weight: 5v5 counts full, 2v2 slightly less (more variance)
        gt_weight = _GAME_TYPE_WEIGHT.get(game.game_type, 1.0)
        lr = 1.0 - alpha
        lr *= gt_weight
        alpha = 1.0 - lr

        new_rating = alpha * old_rating + lr * game_rating
        new_rating = round(min(max(new_rating, 1.0), 10.0), 2)

        user.ai_skill_rating = new_rating
        total_games = user.games_played + user.challenge_wins + user.challenge_losses
        user.skill_confidence = compute_confidence(total_games, rating_hist + [new_rating])

        db.add(SkillHistory(
            user_id=user.id,
            game_id=game.id,
            old_rating=old_rating,
            new_rating=new_rating,
            game_type=game.game_type,
        ))
    db.commit()
