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
    DraftKings / FanDuel Implied Probability via Point Spread.
    """
    skill_diff = rating_a - rating_b
    point_spread = skill_diff * 4.5  # 1.0 skill point = 4.5 points on the scoreboard
    
    # Sportsbook vig-free math: Probability = 1 / (1 + 10^(-Spread / 15))
    win_prob = 1.0 / (1.0 + 10 ** (-point_spread / 15.0))
    return max(0.01, min(0.99, win_prob))


def calculate_betting_lines(win_prob: float) -> dict:
    """
    Converts win probability into American Odds (+200, -150) and Point Spreads.
    Uses inverse Sigmoid for spread and standard probability -> odds math.
    """
    # 1. American Odds (assuming no-juice/vig-free)
    if win_prob >= 0.5:
        # Favorite: Odds = -(p / (1-p)) * 100
        # For p=0.75, odds = -300
        if win_prob > 0.99: odds = -10000
        else: odds = int(-(win_prob / (1.0 - win_prob)) * 100)
    else:
        # Underdog: Odds = ((1-p) / p) * 100
        # For p=0.25, odds = +300
        if win_prob < 0.01: odds = 10000
        else: odds = int(((1.0 - win_prob) / win_prob) * 100)
        
    # 2. Point Spread Approximation
    # Inverse of: win_prob = 1 / (1 + 10^(-spread / 15))
    # spread = -15 * log10(1/win_prob - 1)
    if 0.001 < win_prob < 0.999:
        spread = -15.0 * math.log10(1.0 / win_prob - 1.0)
    else:
        spread = -20.0 if win_prob >= 0.5 else 20.0
        
    # Standard betting format: Favorite is negative (-7.5), Underdog is positive (+2.1)
    # Our formula currently gives positive for win > 0.5, so we flip.
    betting_spread = -round(spread, 1)
    if betting_spread == 0: betting_spread = 0.0 # avoid -0.0
    
    return {
        "win_probability": round(win_prob, 3),
        "moneyline": f"{'+' if odds > 0 else ''}{odds}",
        "spread": f"{'+' if betting_spread > 0 else ''}{betting_spread}"
    }


def _position_entropy(positions: list[str]) -> float:
    from collections import Counter
    if not positions:
        return 0.0
    counts = Counter(p or "SF" for p in positions)
    n = len(positions)
    entropy = -sum((c / n) * math.log2(c / n + 1e-9) for c in counts.values())
    return min(entropy / 2.5, 1.0)


def _team_features(db: Session, participants: list[GameParticipant], game_type: str) -> dict:
    from app.models import SkillHistory
    from datetime import datetime, timezone, timedelta
    
    skills, heights, positions, weights = [], [], [], []
    ppg = rpg = apg = 0.0
    wins = total_games = 0
    hot_streak = 0.0
    
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    
    for p in participants:
        u = p.user
        if not u:
            continue
        skills.append(u.ai_skill_rating or 5.0)
        heights.append(_parse_height(u.height))
        weights.append(float(u.weight) if u.weight else 180.0)
        
        # Calculate hot week momentum
        history_week = db.query(SkillHistory).filter(
            SkillHistory.user_id == u.id,
            SkillHistory.timestamp >= one_week_ago
        ).order_by(SkillHistory.timestamp.asc()).all()
        
        if len(history_week) > 1:
            hot_streak += (history_week[-1].new_rating - history_week[0].old_rating)
            
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
    avg_weight = sum(weights) / len(weights) if weights else 180.0
    win_rate = wins / max(total_games, 1)
    
    # Calculate a composite synergy/efficiency proxy utilizing True Shooting concepts
    team_eff = (ppg / n) * 1.5 + (rpg / n) * 1.2 + (apg / n) * 1.5
    pos_entropy = _position_entropy(positions)

    return {
        "avg_skill": avg_skill, "avg_height": avg_height, "avg_weight": avg_weight,
        "ppg": ppg / n, "rpg": rpg / n, "apg": apg / n,
        "win_rate": win_rate, "total_games": total_games,
        "skill_std": skill_std, "pos_entropy": pos_entropy,
        "synergy_eff": team_eff * (1.0 + pos_entropy * 0.2), # Reward balanced spacing
        "hot_week": hot_streak / n
    }


def _build_feature_vector(db: Session, team_a: list, team_b: list, game_type: str) -> list[float]:
    fa = _team_features(db, team_a, game_type)
    fb = _team_features(db, team_b, game_type)
    return [
        fa["avg_skill"] - fb["avg_skill"], 
        fa["avg_height"] - fb["avg_height"],
        fa["avg_weight"] - fb["avg_weight"],
        fa["ppg"] - fb["ppg"], 
        fa["rpg"] - fb["rpg"], 
        fa["apg"] - fb["apg"],
        fa["win_rate"] - fb["win_rate"], 
        (fa["total_games"] - fb["total_games"]) / 50.0,
        fa["skill_std"], 
        fb["skill_std"], 
        fa["pos_entropy"], 
        fb["pos_entropy"],
        fa["synergy_eff"] - fb["synergy_eff"],
        fa["hot_week"],
        fb["hot_week"],
        1.0 if game_type == "5v5" else 0.0, 
        1.0 if game_type == "3v3" else 0.0,
    ]


def predict_win_probability(db: Session, game: Game, team_a: list, team_b: list) -> float:
    """P(Team A wins). Gradient Boosting when trained; else Elo fallback. Always 0–1."""
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
            raw = 0.7 * prob + 0.3 * elo_prob
            return max(0.0, min(1.0, raw))
        except Exception:
            pass
    return max(0.0, min(1.0, elo_prob))


def online_train(db: Session) -> dict:
    """
    Dynamic Self-Healing ML Engine Setup:
    Periodically loads the `nba_training_data.csv` historical base, merges it with highly-localized
    CoRec app completions, and retrains the entire Scikit-Learn Gradient Boosting Classifier natively.
    """
    try:
        from sklearn.ensemble import GradientBoostingClassifier
        import numpy as np
        import pandas as pd
        from sqlalchemy.orm import joinedload
    except ImportError:
        return {"error": "scikit-learn or pandas required"}

    X, y = [], []

    # 1. Load empirical NBA 30-Year History if available
    nba_csv_path = Path(__file__).parent.parent.parent / "nba_training_data.csv"
    nba_count = 0
    if nba_csv_path.exists():
        try:
            df = pd.read_csv(nba_csv_path)
            for _, row in df.iterrows():
                # Extract precise ordered features
                feats = [
                    row['skill_diff'], row['height_diff'], row['weight_diff'],
                    row['ppg_diff'], row['rpg_diff'], row['apg_diff'],
                    row['win_rate_diff'], row['total_games_diff'],
                    row['skill_std_a'], row['skill_std_b'],
                    row['pos_entropy_a'], row['pos_entropy_b'],
                    row['synergy_diff'], row['hot_week_a'], row['hot_week_b'],
                    row['is_5v5'], row['is_3v3']
                ]
                X.append(feats)
                y.append(int(row['team_a_won']))
            nba_count = len(X)
        except Exception as e:
            print("Failed tracking NBA CSV:", e)

    # 2. Extract actual localized App History natively from DB
    app_count = 0
    games = (
        db.query(Game)
        .filter(Game.status == "completed")
        .filter(Game.team_a_score.isnot(None), Game.team_b_score.isnot(None))
        .all()
    )
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
            app_count += 1
        except Exception:
            continue

    total_games = len(X)
    if total_games < 10:
        return {"games": total_games, "trained": False, "msg": "Insufficient data"}

    X_arr, y_arr = np.array(X), np.array(y)
    
    # Train heavily regularized classifier to avoid overfitting to the large static NBA data
    model = GradientBoostingClassifier(
        n_estimators=150, 
        max_depth=5, 
        learning_rate=0.05, 
        min_samples_leaf=4, 
        subsample=0.85, 
        random_state=42
    )
    model.fit(X_arr, y_arr)
    acc = model.score(X_arr, y_arr)
    
    TEAM_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    import pickle
    with open(TEAM_MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
        
    return {
        "nba_games_used": nba_count,
        "app_games_used": app_count,
        "total": total_games,
        "training_accuracy": round(acc, 4),
        "trained": True
    }
