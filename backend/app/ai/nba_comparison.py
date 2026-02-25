import os
import csv
import math
import pandas as pd

# We prioritized a new extended dataset with height/weight/position
NBA_DATA_PATH = os.path.join(os.path.dirname(__file__), "nba_players_extended.csv")
# Fallback to older dataset if needed
NBA_FALLBACK_PATH = os.path.join(os.path.dirname(__file__), "nbaNew.csv")

def get_nba_comparison(user_stats: dict, user_physicals: dict = None, preferred_position: str = None) -> dict:
    """
    Finds the most similar NBA player using 'Relative Stat Signatures'.
    Instead of raw volume, we compare the shape of the stat distribution
    and incorporate physical metrics (height/weight).
    """
    path = NBA_DATA_PATH if os.path.exists(NBA_DATA_PATH) else NBA_FALLBACK_PATH
    if not os.path.exists(path):
        return {"name": "Unknown Player", "similarity": 0.0, "reason": "NBA data not found."}
        
    # 1. Prepare User Signature
    u_pts = float(user_stats.get("pts", 0))
    u_reb = float(user_stats.get("reb", 0))
    u_ast = float(user_stats.get("ast", 0))
    u_stl = float(user_stats.get("stl", 0))
    u_blk = float(user_stats.get("blk", 0))
    
    # 2. Incorporate User Physicals (if available)
    # Default to 6'4" 200lbs if not provided
    u_height = float(user_physicals.get("height_inches", 76.0)) if user_physicals else 76.0
    u_weight = float(user_physicals.get("weight_lbs", 200.0)) if user_physicals else 200.0
    
    # 3. Calculate Signature (Ratios)
    # This ensures a "pass-first point guard" at the CoRec matches a "pass-first point guard" in the NBA
    total_volume = u_pts + u_reb + u_ast + u_stl + u_blk
    if total_volume < 1.0:
        return {"name": "Rookie", "similarity": 60.0, "reason": "Play more games to unlock your NBA match!"}
        
    u_sig = {
        "pts": u_pts / total_volume,
        "reb": u_reb / total_volume,
        "ast": u_ast / total_volume,
        "def": (u_stl + u_blk) / total_volume
    }

    best_match = None
    min_dist = float('inf')
    
    # Load NBA data
    try:
        df = pd.read_csv(path)
    except Exception:
        return {"name": "System Down", "similarity": 0.0}

    for _, row in df.iterrows():
        try:
            # Map column names based on which file we found
            is_ext = "HEIGHT_INCHES" in row
            name = row["PLAYER_NAME"] if is_ext else row.get("PlayerName", "").split("\\")[0]
            
            pts = float(row["PTS"])
            reb = float(row["REB"]) if is_ext else float(row["TRB"])
            ast = float(row["AST"])
            stl = float(row["STL"])
            blk = float(row["BLK"])
            
            nba_height = float(row["HEIGHT_INCHES"]) if is_ext else 78.0 # Default 6'6"
            nba_weight = float(row["WEIGHT_LBS"]) if is_ext else 215.0 # Default 215lb
            
            # NBA Signature
            nba_vol = pts + reb + ast + stl + blk
            if nba_vol < 1.0: continue
            
            nba_sig = {
                "pts": pts / nba_vol,
                "reb": reb / nba_vol,
                "ast": ast / nba_vol,
                "def": (stl + blk) / nba_vol
            }
            
            # Calculate Signature Distance (Euclidean on Ratios)
            sig_dist = math.sqrt(
                ((u_sig["pts"] - nba_sig["pts"]) * 1.5) ** 2 +
                ((u_sig["reb"] - nba_sig["reb"]) * 1.2) ** 2 +
                ((u_sig["ast"] - nba_sig["ast"]) * 1.8) ** 2 + # Playmaking is a strong fingerprint
                ((u_sig["def"] - nba_sig["def"]) * 2.0) ** 2   # Defense is a strong fingerprint
            )
            
            # Calculate Physical Distance (Normalized)
            # 5 inches difference is large, 30 lbs is large
            phys_dist = math.sqrt(
                ((u_height - nba_height) / 5.0) ** 2 +
                ((u_weight - nba_weight) / 30.0) ** 2
            )
            
            # Position Penalty (Mismatching Guard to Center is bad)
            pos_penalty = 0.0
            if preferred_position and "POSITION" in row:
                nba_pos = row["POSITION"].upper()
                # Center should ideally match Center/Forward
                if preferred_position == "C" and "CENTER" not in nba_pos and "FORWARD" not in nba_pos:
                    pos_penalty = 0.5
                # PG should ideally match Guard
                elif preferred_position == "PG" and "GUARD" not in nba_pos:
                    pos_penalty = 0.5
            
            # Combined Weighted Distance (Playstyle 50%, Physicals 40%, Position 10%)
            # Increased physical weight to ensure height matters more (Victor Wembanyama rule)
            total_dist = (sig_dist * 0.5) + (phys_dist * 0.4) + pos_penalty
            
            if total_dist < min_dist:
                min_dist = total_dist
                # Similarity mapping: 0.0 dist -> 99%, 1.0 dist -> 80%, etc.
                sim_score = round(max(50.0, min(99.0, 100.0 - (total_dist * 12))), 1)
                
                best_match = {
                    "name": name,
                    "similarity": sim_score,
                    "team": row["TEAM_ABBREVIATION"] if is_ext else row.get("Team", "NBA"),
                    "position": row["POSITION"] if is_ext else row.get("Pos", "G/F")
                }
        except (ValueError, KeyError):
            continue

    if not best_match:
        return {"name": "G-League Prospect", "similarity": 75.0}

    return best_match
