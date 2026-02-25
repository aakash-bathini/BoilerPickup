"""
NBA playstyle comparison for C, PF, SF, SG, PG.
Uses position height tiers (male/female), stat signatures, and physical metrics.
Games to 15 (pickup) — stat ratios matter, not raw volume.
"""
import os
import math
import pandas as pd

from app.ai.nba_position_tiers import (
    get_user_expected_height,
    nba_height_in_range_for_position,
    position_match_penalty,
)

NBA_DATA_PATH = os.path.join(os.path.dirname(__file__), "nba_players_extended.csv")
NBA_FALLBACK_PATH = os.path.join(os.path.dirname(__file__), "nbaNew.csv")

_NBA_DF_CACHE = None


def _load_nba_df():
    """Load NBA data once and cache for fast repeated lookups."""
    global _NBA_DF_CACHE
    if _NBA_DF_CACHE is not None:
        return _NBA_DF_CACHE
    path = NBA_DATA_PATH if os.path.exists(NBA_DATA_PATH) else NBA_FALLBACK_PATH
    if not os.path.exists(path):
        return None
    try:
        _NBA_DF_CACHE = pd.read_csv(path)
        return _NBA_DF_CACHE
    except Exception:
        return None


def get_nba_comparison(
    user_stats: dict,
    user_physicals: dict = None,
    preferred_position: str = None,
    gender: str = None,
    skill_rating: float = None,
) -> dict:
    """
    Finds the most similar NBA player. Normalized: best amateurs → star NBA players,
    weaker amateurs → role players. Uses stat signatures + position tiers.
    """
    if not os.path.exists(NBA_DATA_PATH) and not os.path.exists(NBA_FALLBACK_PATH):
        return {"name": "Unknown Player", "similarity": 0.0, "reason": "NBA data not found."}

    u_pts = float(user_stats.get("pts", 0))
    u_reb = float(user_stats.get("reb", 0))
    u_ast = float(user_stats.get("ast", 0))
    u_stl = float(user_stats.get("stl", 0))
    u_blk = float(user_stats.get("blk", 0))

    u_height = float(user_physicals.get("height_inches", 0)) if user_physicals else 0
    if u_height <= 0:
        u_height = get_user_expected_height(gender, preferred_position)
    u_weight = float(user_physicals.get("weight_lbs", 200.0)) if user_physicals else 200.0

    total_volume = u_pts + u_reb + u_ast + u_stl + u_blk
    if total_volume < 1.0:
        return {"name": "Rookie", "similarity": 60.0, "reason": "Play more games to unlock your NBA match!"}

    u_sig = {
        "pts": u_pts / total_volume,
        "reb": u_reb / total_volume,
        "ast": u_ast / total_volume,
        "def": (u_stl + u_blk) / total_volume,
    }

    best_match = None
    min_dist = float("inf")

    df = _load_nba_df()
    if df is None:
        return {"name": "System Down", "similarity": 0.0}

    for _, row in df.iterrows():
        try:
            is_ext = "HEIGHT_INCHES" in row
            name = row["PLAYER_NAME"] if is_ext else row.get("PlayerName", "").split("\\")[0]

            pts = float(row["PTS"])
            reb = float(row["REB"]) if is_ext else float(row["TRB"])
            ast = float(row["AST"])
            stl = float(row["STL"])
            blk = float(row["BLK"])

            nba_height = float(row["HEIGHT_INCHES"]) if is_ext else 78.0
            nba_weight = float(row["WEIGHT_LBS"]) if is_ext else 215.0
            nba_pos_str = str(row.get("POSITION", row.get("Pos", "")))

            if not nba_height_in_range_for_position(nba_height, preferred_position):
                continue

            nba_vol = pts + reb + ast + stl + blk
            if nba_vol < 1.0:
                continue

            nba_sig = {
                "pts": pts / nba_vol,
                "reb": reb / nba_vol,
                "ast": ast / nba_vol,
                "def": (stl + blk) / nba_vol,
            }

            sig_dist = math.sqrt(
                ((u_sig["pts"] - nba_sig["pts"]) * 1.5) ** 2
                + ((u_sig["reb"] - nba_sig["reb"]) * 1.2) ** 2
                + ((u_sig["ast"] - nba_sig["ast"]) * 1.8) ** 2
                + ((u_sig["def"] - nba_sig["def"]) * 2.0) ** 2
            )

            phys_dist = math.sqrt(
                ((u_height - nba_height) / 5.0) ** 2 + ((u_weight - nba_weight) / 30.0) ** 2
            )

            pos_penalty = position_match_penalty(nba_pos_str, preferred_position)

            # Tier normalization: NBA CSV has per-game stats. Stars ~45-55, role ~15-25.
            # High-skill amateurs → star NBA players; low-skill → role players.
            skill = float(skill_rating) if skill_rating is not None else 5.0
            nba_vol_norm = min(1.0, nba_vol / 50.0)  # Per-game PTS+REB+AST+STL+BLK; stars ~50
            if skill >= 7.0:
                tier_penalty = 0.25 * (1.0 - nba_vol_norm)  # Strongly prefer stars for elite amateurs
            elif skill >= 5.5:
                tier_penalty = 0.12 * (1.0 - nba_vol_norm)  # Mild preference for above-average
            elif skill <= 3.0:
                tier_penalty = 0.2 * nba_vol_norm  # Prefer role players for beginners
            else:
                tier_penalty = 0.05 * abs(nba_vol_norm - 0.5)  # Mid-skill: slight preference for mid-tier

            total_dist = (sig_dist * 0.5) + (phys_dist * 0.4) + pos_penalty + tier_penalty

            if total_dist < min_dist:
                min_dist = total_dist
                sim_score = round(max(50.0, min(99.0, 100.0 - (total_dist * 12))), 1)
                best_match = {
                    "name": name,
                    "similarity": sim_score,
                    "team": row["TEAM_ABBREVIATION"] if is_ext else row.get("Team", "NBA"),
                    "position": row["POSITION"] if is_ext else row.get("Pos", "G/F"),
                }
        except (ValueError, KeyError):
            continue

    if not best_match:
        return {"name": "G-League Prospect", "similarity": 75.0}

    return best_match
