"""
Synthetic data generator for training and evaluation.

Generates:
  - 100 synthetic players with latent true skill ~ Uniform(1, 10)
  - 500+ simulated games across 5v5, 3v3, 2v2
  - Stats conditioned on true skill (higher skill -> higher FG%, more AST, fewer TOV)
  - Outcomes determined by team skill differential + noise

Produces training data + evaluation baselines.
"""
import math
import random
import json
import os

import numpy as np

from app.ai.skill_model import SkillModel, train_on_games, STAT_DIM


def generate_players(n: int = 100) -> list[dict]:
    players = []
    for i in range(n):
        true_skill = random.uniform(1.0, 10.0)
        noise = random.gauss(0, 1.0)
        self_reported = max(1, min(10, round(true_skill + noise)))

        positions = ["PG", "SG", "SF", "PF", "C"]
        position = random.choice(positions)

        players.append({
            "id": i,
            "true_skill": true_skill,
            "self_reported_skill": self_reported,
            "position": position,
            "games_played": 0,
            "wins": 0,
            "losses": 0,
            "elo": 1500.0,
        })
    return players


def generate_game_stats(player: dict, game_type: str, won: bool) -> dict:
    """Generate realistic box score stats conditioned on true skill."""
    skill = player["true_skill"]

    pts_base = skill * 1.5 + random.gauss(0, 2)
    reb_base = skill * 0.6 + random.gauss(0, 1.5)
    ast_base = skill * 0.4 + random.gauss(0, 1)
    stl_base = skill * 0.15 + random.gauss(0, 0.5)
    blk_base = skill * 0.1 + random.gauss(0, 0.4)
    tov_base = max(0, (10 - skill) * 0.3 + random.gauss(0, 0.5))

    type_scale = {"5v5": 1.0, "3v3": 1.2, "2v2": 1.4}
    scale = type_scale.get(game_type, 1.0)

    pts = max(0, round(pts_base * scale))
    reb = max(0, round(reb_base * scale))
    ast = max(0, round(ast_base * scale))
    stl = max(0, round(stl_base))
    blk = max(0, round(blk_base))
    tov = max(0, round(tov_base))

    fg_pct = min(0.65, max(0.2, 0.3 + skill * 0.03 + random.gauss(0, 0.05)))
    fga = max(1, round(pts / max(fg_pct * 2, 0.5)))
    fgm = max(0, min(fga, round(fga * fg_pct)))

    three_pct = min(0.5, max(0.1, 0.2 + skill * 0.025 + random.gauss(0, 0.05)))
    three_pa = max(0, round(fga * 0.3))
    three_pm = max(0, min(three_pa, round(three_pa * three_pct)))

    ft_pct = min(0.9, max(0.4, 0.5 + skill * 0.04 + random.gauss(0, 0.05)))
    fta = max(0, round(pts * 0.15))
    ftm = max(0, min(fta, round(fta * ft_pct)))

    if won:
        pts = max(pts, pts + random.randint(0, 2))

    return {
        "pts": pts, "reb": reb, "ast": ast,
        "stl": stl, "blk": blk, "tov": tov,
        "fgm": fgm, "fga": fga,
        "three_pm": three_pm, "three_pa": three_pa,
        "ftm": ftm, "fta": fta,
    }


def compute_team_totals(team_stats: list[dict]) -> dict:
    return {
        "pts": max(1, sum(s["pts"] for s in team_stats)),
        "reb": max(1, sum(s["reb"] for s in team_stats)),
        "ast": max(1, sum(s["ast"] for s in team_stats)),
    }


def stats_to_feature_vector(stats: dict, team_totals: dict, game_type: str) -> list[float]:
    pts_norm = stats["pts"] / max(team_totals["pts"], 1)
    reb_norm = stats["reb"] / max(team_totals["reb"], 1)
    ast_norm = stats["ast"] / max(team_totals["ast"], 1)

    fg_eff = (stats["fgm"] + 1) / (stats["fga"] + 2)
    three_eff = (stats["three_pm"] + 1) / (stats["three_pa"] + 2)
    ft_eff = (stats["ftm"] + 1) / (stats["fta"] + 2)

    gt = [0.0, 0.0, 0.0]
    if game_type == "5v5":
        gt[0] = 1.0
    elif game_type == "3v3":
        gt[1] = 1.0
    elif game_type == "2v2":
        gt[2] = 1.0

    return [
        pts_norm, reb_norm, ast_norm,
        float(stats["stl"]), float(stats["blk"]), float(stats["tov"]),
        fg_eff, three_eff, ft_eff,
    ] + gt


def simulate_games(players: list[dict], n_games: int = 500) -> list[dict]:
    """Simulate games and return training data."""
    games = []
    game_types = ["5v5", "3v3", "2v2"]
    team_sizes = {"5v5": 5, "3v3": 3, "2v2": 2}

    for _ in range(n_games):
        game_type = random.choice(game_types)
        team_size = team_sizes[game_type]
        total_needed = team_size * 2

        if len(players) < total_needed:
            continue

        selected = random.sample(players, total_needed)
        team_a_players = selected[:team_size]
        team_b_players = selected[team_size:]

        team_a_skill = np.mean([p["true_skill"] for p in team_a_players])
        team_b_skill = np.mean([p["true_skill"] for p in team_b_players])

        skill_diff = team_a_skill - team_b_skill
        win_prob_a = 1.0 / (1.0 + math.exp(-skill_diff * 0.5))
        team_a_won = random.random() < win_prob_a

        team_a_stats = [generate_game_stats(p, game_type, team_a_won) for p in team_a_players]
        team_b_stats = [generate_game_stats(p, game_type, not team_a_won) for p in team_b_players]

        team_a_totals = compute_team_totals(team_a_stats)
        team_b_totals = compute_team_totals(team_b_stats)

        team_a_features = [stats_to_feature_vector(s, team_a_totals, game_type) for s in team_a_stats]
        team_b_features = [stats_to_feature_vector(s, team_b_totals, game_type) for s in team_b_stats]

        for p in team_a_players:
            p["games_played"] += 1
            if team_a_won:
                p["wins"] += 1
            else:
                p["losses"] += 1

        for p in team_b_players:
            p["games_played"] += 1
            if not team_a_won:
                p["wins"] += 1
            else:
                p["losses"] += 1

        games.append({
            "team_a_ids": [p["id"] for p in team_a_players],
            "team_b_ids": [p["id"] for p in team_b_players],
            "team_a_stats": team_a_features,
            "team_b_stats": team_b_features,
            "team_a_won": team_a_won,
            "game_type": game_type,
            "team_a_true_skill": team_a_skill,
            "team_b_true_skill": team_b_skill,
            "team_a_raw_stats": team_a_stats,
            "team_b_raw_stats": team_b_stats,
        })

    return games


def evaluate_baselines(players: list[dict], games: list[dict]) -> dict:
    """Evaluate all baselines on the simulated games."""

    results = {
        "self_report": {"correct": 0, "total": 0},
        "linear_stats": {"correct": 0, "total": 0},
        "elo": {"correct": 0, "total": 0},
        "neural": {"correct": 0, "total": 0},
    }

    elo_ratings = {p["id"]: 1500.0 for p in players}
    K = 32

    from app.ai.skill_model import get_model
    model = get_model()

    for game in games:
        actual = game["team_a_won"]
        a_ids = game["team_a_ids"]
        b_ids = game["team_b_ids"]
        a_raw = game.get("team_a_raw_stats", [])
        b_raw = game.get("team_b_raw_stats", [])

        player_map = {p["id"]: p for p in players}

        # Baseline 1: Self-reported skill
        a_self = np.mean([player_map[pid]["self_reported_skill"] for pid in a_ids])
        b_self = np.mean([player_map[pid]["self_reported_skill"] for pid in b_ids])
        pred_self = a_self > b_self
        if pred_self == actual:
            results["self_report"]["correct"] += 1
        results["self_report"]["total"] += 1

        # Baseline 2: Linear weighted stats
        def linear_score(stats_list):
            scores = []
            for s in stats_list:
                score = (
                    s["pts"] * 1.0
                    + s["reb"] * 1.2
                    + s["ast"] * 1.5
                    + s["stl"] * 2.0
                    + s["blk"] * 1.8
                    - s["tov"] * 1.5
                )
                scores.append(score)
            return np.mean(scores) if scores else 0

        if a_raw and b_raw:
            a_linear = linear_score(a_raw)
            b_linear = linear_score(b_raw)
            pred_linear = a_linear > b_linear
            if pred_linear == actual:
                results["linear_stats"]["correct"] += 1
            results["linear_stats"]["total"] += 1

        # Baseline 3: Elo
        a_elo = np.mean([elo_ratings.get(pid, 1500) for pid in a_ids])
        b_elo = np.mean([elo_ratings.get(pid, 1500) for pid in b_ids])
        pred_elo = a_elo > b_elo
        if pred_elo == actual:
            results["elo"]["correct"] += 1
        results["elo"]["total"] += 1

        for pid in a_ids:
            expected = 1.0 / (1.0 + 10 ** ((b_elo - elo_ratings.get(pid, 1500)) / 400))
            outcome = 1.0 if actual else 0.0
            elo_ratings[pid] = elo_ratings.get(pid, 1500) + K * (outcome - expected)

        for pid in b_ids:
            expected = 1.0 / (1.0 + 10 ** ((a_elo - elo_ratings.get(pid, 1500)) / 400))
            outcome = 0.0 if actual else 1.0
            elo_ratings[pid] = elo_ratings.get(pid, 1500) + K * (outcome - expected)

        # Neural model
        try:
            win_prob = model.predict_win_probability(a_ids, b_ids)
            pred_neural = win_prob > 0.5
            if pred_neural == actual:
                results["neural"]["correct"] += 1
            results["neural"]["total"] += 1
        except Exception:
            pass

    # Compute skill convergence (Pearson r between learned skill and true skill)
    true_skills = []
    learned_skills = []
    for p in players:
        if p["games_played"] > 0:
            true_skills.append(p["true_skill"])
            learned_skills.append(model.get_player_skill(p["id"]))

    from scipy.stats import pearsonr
    if len(true_skills) > 2:
        correlation, _ = pearsonr(true_skills, learned_skills)
    else:
        correlation = 0.0

    output = {}
    for name, data in results.items():
        acc = data["correct"] / max(data["total"], 1)
        output[name] = {"accuracy": round(acc, 4), "total_games": data["total"]}

    output["skill_convergence"] = round(correlation, 4)

    return output


def run_full_simulation():
    """Run the complete simulation pipeline."""
    print("=" * 60)
    print("BOILER PICKUP - Synthetic Data Simulation")
    print("=" * 60)

    print("\n[1/4] Generating 100 synthetic players...")
    players = generate_players(100)

    print("[2/4] Simulating 500 games...")
    games = simulate_games(players, 500)
    print(f"       Generated {len(games)} games")

    game_type_counts = {}
    for g in games:
        gt = g["game_type"]
        game_type_counts[gt] = game_type_counts.get(gt, 0) + 1
    for gt, count in sorted(game_type_counts.items()):
        print(f"       {gt}: {count} games")

    print("[3/4] Training neural embedding model...")
    model = SkillModel()

    for p in players:
        model.initialize_player_embedding(p["id"], p["self_reported_skill"])

    from app.ai.skill_model import get_model
    global_model = get_model()
    global_model.load_state_dict(model.state_dict())

    train_result = train_on_games(games, epochs=80, lr=1e-3)
    print(f"       Final loss: {train_result['final_loss']:.4f}")
    print(f"       Final accuracy: {train_result['final_accuracy']:.4f}")

    print("[4/4] Evaluating baselines...")
    eval_results = evaluate_baselines(players, games)

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n{'Model':<25} {'Win Pred. Accuracy':>20}")
    print("-" * 45)
    print(f"{'Self-Reported':<25} {eval_results['self_report']['accuracy']:>20.4f}")
    print(f"{'Linear Weighted Stats':<25} {eval_results['linear_stats']['accuracy']:>20.4f}")
    print(f"{'Elo Rating':<25} {eval_results['elo']['accuracy']:>20.4f}")
    print(f"{'Neural Embedding':<25} {eval_results['neural']['accuracy']:>20.4f}")
    print(f"\nSkill Convergence (Pearson r): {eval_results['skill_convergence']:.4f}")
    print("=" * 60)

    return eval_results


if __name__ == "__main__":
    run_full_simulation()
