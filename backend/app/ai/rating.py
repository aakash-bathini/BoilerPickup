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


def compute_confidence(total_games: int, rating_history: list[float] | None = None) -> float:
    """Glicko-2 inspired Rating Deviation (RD) mapping to confidence."""
    # Base RD shrinks as games increase (capped asymptotically)
    rd_base = 350.0 * math.exp(-total_games / 10.0) + 40.0 
    
    # Volatility penalty if ratings swing wildly
    volatility = 0.0
    if rating_history and len(rating_history) >= 3:
        mean_r = sum(rating_history) / len(rating_history)
        variance = sum((r - mean_r) ** 2 for r in rating_history) / len(rating_history)
        std = math.sqrt(variance)
        # Higher std means higher volatility in performance
        volatility = min(150.0, std * 50.0)
    
    # Final RD proxy (typical Glicko scale)
    rd_proxy = min(350.0, rd_base + volatility)
    
    # Confidence is inversely proportional to RD
    # Glicko RD ranges roughly 30 to 350
    confidence = 1.0 - (rd_proxy - 30.0) / 320.0
    return round(max(0.05, min(0.95, confidence)), 4)


def get_learning_rate(total_games_before: int, current_confidence: float = 0.5) -> float:
    """
    Dynamic learning rate scaling with uncertainty (Glicko-2 inspired).
    Higher uncertainty (lower confidence) -> Higher learning rate.
    """
    K_max = 0.5
    lr = K_max * (1.0 - current_confidence)
    if total_games_before < 3:
        lr = min(lr, 0.25)  # Cap early overreactions
    return max(0.05, lr)


def get_alpha(total_games_before: int, current_confidence: float = 0.5) -> float:
    """Prior weight from learning rate. alpha = 1 - lr (weight on old rating)."""
    lr = get_learning_rate(total_games_before, current_confidence)
    return min(max(1.0 - lr, 0.1), 0.95)


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
    Grad-Level Rating Formula: Implements a custom 'Pickup PER' (Player Efficiency Rating).
    Synthesizes raw box score data into a single efficiency metric that directly 
    modulates the Elo k-factor / match scalar.
    """
    base = _GAME_BASELINES.get(game.game_type, _GAME_BASELINES["5v5"])
    weights = _get_position_weights(preferred_position)

    pts, reb, ast = stats.pts, stats.reb, stats.ast
    stl, blk, tov = stats.stl, stats.blk, stats.tov
    fgm, fga = stats.fgm, stats.fga
    three_pm, ftm, fta = stats.three_pm, stats.ftm, stats.fta

    # 1. Calculate Pickup PER (Unadjusted)
    missed_fg = max(fga - fgm, 0)
    missed_ft = max(fta - ftm, 0)
    
    # PER weights for pickup games (different from standard NBA scale due to game formats)
    per_pts = pts * 1.0
    per_ast = ast * 1.5
    per_reb = reb * 1.2
    per_stl = stl * 2.5
    per_blk = blk * 2.5
    per_tov = tov * -2.0
    per_miss_fg = missed_fg * -1.0
    per_miss_ft = missed_ft * -0.5
    
    raw_per = per_pts + per_ast + per_reb + per_stl + per_blk + per_tov + per_miss_fg + per_miss_ft

    # 2. Positional Normalization (Apply positional importance weights)
    # Centers should be highly penalized for bad rebounding; Guards for TOVs
    w = weights
    normalized_per = (
        (per_pts * w["ppg"]) +
        (per_ast * w["apg"]) +
        (per_reb * w["rpg"]) +
        (per_stl * w["spg"]) +
        (per_blk * w["bpg"]) +
        (per_tov * abs(w["topg"])) # Negative already
    )

    # 3. Efficiency Bonus (True Shooting Variant)
    ts_attempts = 2.0 * (fga + 0.44 * fta + 1)
    ts_pct = pts / ts_attempts if ts_attempts > 0 else 0.5
    eff_bonus = math.tanh((ts_pct - 0.52) * 6)  # Sigmoid-like scaling centered around 52% true shooting

    # 4. Final Game Raw Performance Variable
    # We combine normalized PER and efficiency to get a base modifier before match context
    raw_performance = (normalized_per / max(base["scale"], 1.0)) * (1.0 + eff_bonus * 0.5)
    
    # 5. Math Mapping -> [0.0, 10.0] scale
    # We remove the "forcing to center" logic and use a more linear performance interpretor.
    # An average pickup performance (hitting baselines) is ~7.5 after scaling.
    # We map 0.0 performance to 0.0 rating and 15.0+ performance to 10.0 rating.
    perf_rating = (raw_performance / 15.0) * 10.0
    
    # Apply a slight soft-cap on the ends to prevent extreme outliers from breaking the 1-10 range
    if perf_rating > 9.0:
        perf_rating = 9.0 + (perf_rating - 9.0) * 0.1 # Diminishing returns after 9.0
    elif perf_rating < 1.0:
        perf_rating = 1.0 - (1.0 - perf_rating) * 0.2 # Slower drop at the very bottom

    # 6. Apply Match Context (Score Margin & Opponent Strength)
    # This is the true Elo component: performance relative to competition.
    margin_norm = min(abs(score_margin) / 15.0, 1.0)
    
    # Elo scaling: Overperforming against tougher opponents yields higher ratings.
    # If you play a 9.0 rating team, your performance for that game is weighted higher.
    match_difficulty = 1.0 + (avg_opponent_rating - 5.0) * 0.05
    
    # Winners get a slight performance boost for "clutch factor" / "winning basketball"
    win_bonus = 1.1 if won else 0.9
    
    final_rating = perf_rating * match_difficulty * win_bonus

    # Bound safety guarantees a strict theoretical cap of 0 to 10.
    return round(max(0.0, min(10.0, final_rating)), 2)


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

        alpha = get_alpha(total_before, user.skill_confidence)
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
