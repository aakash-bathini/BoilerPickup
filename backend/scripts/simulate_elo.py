#!/usr/bin/env python3
"""
Verify Elo / win predictor math and simulate rating spread.
Run: python scripts/simulate_elo.py

1. Checks predict_1v1_win_probability for key matchups
2. Simulates rating updates (no DB) to verify 1–10 spread
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.win_predictor import predict_1v1_win_probability, calculate_betting_lines
from app.ai.rating import get_learning_rate, get_alpha, compute_confidence


def main():
    print("=" * 55)
    print("ELO / WIN PREDICTOR VERIFICATION")
    print("=" * 55)

    print("\n1. 1v1 Win Probability (1=bad, 10=good):")
    for ra, rb in [(10.0, 1.0), (9.0, 3.0), (7.0, 5.0), (5.0, 5.0), (3.0, 7.0), (1.0, 10.0)]:
        p = predict_1v1_win_probability(ra, rb)
        lines = calculate_betting_lines(p)
        print(f"   {ra} vs {rb}: P({ra} wins) = {p:.1%}  |  Spread: {lines['spread']}  |  ML: {lines['moneyline']}")

    print("\n2. Learning rate (early vs veteran):")
    for games in [0, 3, 10, 25, 50]:
        lr = get_learning_rate(games, 0.5)
        alpha = get_alpha(games, 0.5)
        print(f"   Games={games:2d}: LR={lr:.3f}, alpha={alpha:.3f} (higher alpha = more weight on old rating)")

    print("\n3. Confidence growth:")
    for games in [0, 5, 15, 30, 60]:
        conf = compute_confidence(games)
        print(f"   Games={games:2d}: confidence={conf:.2%}")

    print("\n4. Simulated rating drift (pure Elo, K=0.3):")
    # 9.0 vs 3.0: expected 9.0 wins ~95%. After 20 games: 9.0 should stay high, 3.0 stay low
    r_high, r_low = 9.0, 3.0
    for _ in range(20):
        p_high = predict_1v1_win_probability(r_high, r_low)
        # High wins
        exp_high = 1.0 / (1.0 + 10.0 ** ((r_low - r_high) / 4.0))
        r_high = min(10.0, r_high + 0.3 * (1.0 - exp_high))
        r_low = max(1.0, r_low - 0.3 * exp_high)
    print(f"   After 20 games (9.0 always beats 3.0): high={r_high:.2f}, low={r_low:.2f}")

    print("\n" + "=" * 55)
    print("To get full 1–10 spread after seeding, run:")
    print("  python scripts/seed_demo_data.py --reset")
    print("  curl -X POST http://localhost:8000/api/train-predictor")
    print("=" * 55)


if __name__ == "__main__":
    main()
