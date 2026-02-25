"""
1v1 and team win probability. Elo-style for 1v1; Gradient Boosting for team games.
"""
import math
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Game, GameParticipant
from app.ai.player_match import _parse_height, _get_career_stats

# Team win predictor model path
TEAM_MODEL_PATH = Path(__file__).parent.parent.parent / "win_predictor_model.pkl"


def predict_1v1_win_probability(rating_a: float, rating_b: float) -> float:
    """
    P(player A beats player B) using Elo-style logistic.
    Scale 1-10, divisor 4 for sensitivity.
    """
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 4.0))


def _position_entropy(positions: list[str]) -> float:
    from collections import Counter
    if not positions:
        return 0.0
    counts = Counter(p or "SF" for p in positions)
    n = len(positions)
    entropy = -sum((c / n) * math.log2(c / n + 1e-9) for c in counts.values())
    return min(entropy / 2.5, 1.0)


def _team_features(db: Session, participants: list[GameParticipant], game_type: str) -> dict:
    skills, heights, positions = [], [], []
    ppg = rpg = apg = 0.0
    wins = total_games = 0
    for p in participants:
        u = p.user
        if not u:
            continue
        skills.append(u.ai_skill_rating or 5.0)
        heights.append(_parse_height(u.height))
        stats = _get_career_stats(db, u.id)
        ppg += stats["ppg"]
        rpg += stats["rpg"]
        apg += stats["apg"]
        tg = u.games_played + u.challenge_wins + u.challenge_losses
        total_games += tg
        wins += u.wins + u.challenge_wins
        positions.append(u.preferred_position)
    n = max(len(participants), 1)
    avg_skill = sum(skills) / len(skills) if skills else 5.0
    skill_std = (sum((s - avg_skill) ** 2 for s in skills) / len(skills)) ** 0.5 if len(skills) > 1 else 0.0
    avg_height = sum(heights) / len(heights) if heights else 70.0
    win_rate = wins / max(total_games, 1)
    return {
        "avg_skill": avg_skill, "avg_height": avg_height,
        "ppg": ppg / n, "rpg": rpg / n, "apg": apg / n,
        "win_rate": win_rate, "total_games": total_games,
        "skill_std": skill_std, "pos_entropy": _position_entropy(positions),
    }


def _build_feature_vector(db: Session, team_a: list, team_b: list, game_type: str) -> list[float]:
    fa = _team_features(db, team_a, game_type)
    fb = _team_features(db, team_b, game_type)
    return [
        fa["avg_skill"] - fb["avg_skill"], fa["avg_height"] - fb["avg_height"],
        fa["ppg"] - fb["ppg"], fa["rpg"] - fb["rpg"], fa["apg"] - fb["apg"],
        fa["win_rate"] - fb["win_rate"], (fa["total_games"] - fb["total_games"]) / 50.0,
        fa["skill_std"], fb["skill_std"], fa["pos_entropy"], fb["pos_entropy"],
        1.0 if game_type == "5v5" else 0.0, 1.0 if game_type == "3v3" else 0.0,
    ]


def predict_win_probability(db: Session, game: Game, team_a: list, team_b: list) -> float:
    """P(Team A wins). Gradient Boosting when trained; else Elo fallback."""
    if not team_a or not team_b:
        return 0.5
    fa = _team_features(db, team_a, game.game_type)
    fb = _team_features(db, team_b, game.game_type)
    elo_prob = predict_1v1_win_probability(fa["avg_skill"], fb["avg_skill"])
    if TEAM_MODEL_PATH.exists():
        try:
            import pickle
            import numpy as np
            with open(TEAM_MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            X = np.array([_build_feature_vector(db, team_a, team_b, game.game_type)])
            prob = float(model.predict_proba(X)[0][1])
            return 0.7 * prob + 0.3 * elo_prob
        except Exception:
            pass
    return elo_prob


def train_on_games(db: Session, min_games: int = 20) -> dict:
    """Train team win predictor on completed games."""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        import numpy as np
        from sqlalchemy.orm import joinedload
    except ImportError:
        return {"error": "scikit-learn required"}

    games = (
        db.query(Game)
        .filter(Game.status == "completed")
        .filter(Game.team_a_score.isnot(None), Game.team_b_score.isnot(None))
        .all()
    )
    if len(games) < min_games:
        return {"games": len(games), "min_required": min_games, "trained": False}

    X, y = [], []
    for g in games:
        participants = (
            db.query(GameParticipant)
            .options(joinedload(GameParticipant.user))
            .filter(GameParticipant.game_id == g.id)
            .all()
        )
        team_a = [p for p in participants if p.team == "A"]
        team_b = [p for p in participants if p.team == "B"]
        if not team_a or not team_b:
            continue
        try:
            X.append(_build_feature_vector(db, team_a, team_b, g.game_type))
            y.append(1 if (g.team_a_score or 0) > (g.team_b_score or 0) else 0)
        except Exception:
            continue

    if len(X) < min_games:
        return {"games": len(X), "min_required": min_games, "trained": False}

    X_arr, y_arr = np.array(X), np.array(y)
    X_train, X_test, y_train, y_test = train_test_split(X_arr, y_arr, test_size=0.2, random_state=42)
    model = GradientBoostingClassifier(n_estimators=100, max_depth=4, learning_rate=0.1, min_samples_leaf=2, random_state=42)
    model.fit(X_train, y_train)
    acc = model.score(X_test, y_test)
    TEAM_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import pickle
    with open(TEAM_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    return {"games": len(X), "accuracy": round(acc, 4), "trained": True}
