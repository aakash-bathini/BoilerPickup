"""
Team balancing algorithm.

When a game roster is full and the creator clicks "Start":
1. Retrieve all player embeddings for participants
2. Generate candidate team splits (exhaustive for 2v2/3v3, sampled for 5v5)
3. For each split, compute Imbalance = |P(A wins) - 0.5|
4. Select the split that minimizes imbalance
5. Fallback: greedy alternating by scalar ai_skill_rating

Works with player_match.py: both use ai_skill_rating from rating.py.
- matchmaking: balances teams at game start (who plays with whom)
- player_match: find_matches (similar players), find_complementary_teammates (teaming up)
"""
import math
import random
from itertools import combinations

from sqlalchemy.orm import Session

from app.models import Game, GameParticipant


def assign_teams(db: Session, game: Game, participants: list[GameParticipant]):
    """
    Assign balanced teams using the trained model when available,
    falling back to greedy skill-sort.
    """
    try:
        from app.ai.skill_model import get_model
        model = get_model()
        _assign_with_model(model, game, participants)
    except Exception:
        _greedy_assign(participants)


def _assign_with_model(model, game: Game, participants: list[GameParticipant]):
    """Use the trained model to find the most balanced split."""
    n = len(participants)
    team_size = n // 2
    player_ids = [p.user_id for p in participants]

    if n <= 6:
        splits = list(combinations(range(n), team_size))
    else:
        all_combos = list(combinations(range(n), team_size))
        max_samples = min(len(all_combos), 500)
        splits = random.sample(all_combos, max_samples)

    best_split = None
    best_imbalance = float("inf")

    for team_a_indices in splits:
        team_b_indices = [i for i in range(n) if i not in team_a_indices]

        team_a_ids = [player_ids[i] for i in team_a_indices]
        team_b_ids = [player_ids[i] for i in team_b_indices]

        try:
            win_prob = model.predict_win_probability(team_a_ids, team_b_ids)
        except Exception:
            continue

        imbalance = abs(win_prob - 0.5)

        if imbalance < best_imbalance:
            best_imbalance = imbalance
            best_split = (set(team_a_indices), set(team_b_indices))

    if best_split is None:
        _greedy_assign(participants)
        return

    team_a_set, team_b_set = best_split
    for i, p in enumerate(participants):
        p.team = "A" if i in team_a_set else "B"

    # Safety: if any participant was missed, fall back to greedy
    if any((p.team or "").lower() not in ("a", "b") for p in participants):
        _greedy_assign(participants)


def _greedy_assign(participants: list[GameParticipant]):
    """Minimize skill imbalance: for n<=6 try all splits, else greedy alternate."""
    n = len(participants)
    team_size = n // 2
    skills = [p.user.ai_skill_rating if p.user else 5.0 for p in participants]

    if n <= 6:
        best_imbalance = float("inf")
        best_split = None
        for team_a_indices in combinations(range(n), team_size):
            team_b_indices = [i for i in range(n) if i not in team_a_indices]
            sum_a = sum(skills[i] for i in team_a_indices)
            sum_b = sum(skills[i] for i in team_b_indices)
            imb = abs(sum_a - sum_b)
            if imb < best_imbalance:
                best_imbalance = imb
                best_split = (set(team_a_indices), set(team_b_indices))
        if best_split:
            for i, p in enumerate(participants):
                p.team = "A" if i in best_split[0] else "B"
            return

    sorted_p = sorted(
        participants,
        key=lambda p: p.user.ai_skill_rating if p.user else 0,
        reverse=True,
    )
    team_a_skill = 0.0
    team_b_skill = 0.0
    for p in sorted_p:
        skill = p.user.ai_skill_rating if p.user else 5.0
        if team_a_skill <= team_b_skill:
            p.team = "A"
            team_a_skill += skill
        else:
            p.team = "B"
            team_b_skill += skill


def get_preview_split(participants: list[GameParticipant]) -> tuple[list[GameParticipant], list[GameParticipant]]:
    """
    Return (team_a, team_b) for a full roster without persisting.
    Uses same skill-balancing logic as greedy assignment.
    Used for win predictor when game is full but not yet started.
    """
    sorted_p = sorted(
        participants,
        key=lambda p: p.user.ai_skill_rating if p.user else 0,
        reverse=True,
    )
    team_a, team_b = [], []
    team_a_skill = 0.0
    team_b_skill = 0.0
    for p in sorted_p:
        skill = p.user.ai_skill_rating if p.user else 5.0
        if team_a_skill <= team_b_skill:
            team_a.append(p)
            team_a_skill += skill
        else:
            team_b.append(p)
            team_b_skill += skill
    return team_a, team_b


def compute_team_imbalance(model, team_a_ids: list[int], team_b_ids: list[int]) -> float:
    """Return |P(A wins) - 0.5| for a given split."""
    try:
        win_prob = model.predict_win_probability(team_a_ids, team_b_ids)
        return abs(win_prob - 0.5)
    except Exception:
        return 0.5
