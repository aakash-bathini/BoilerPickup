"""
Build nba_players_extended.csv from nbaNew.csv by:
1. Loading all unique players from nbaNew (deduplicated by name)
2. Fetching height/weight from nba_api for each player
3. Outputting extended format with proper height data for classification

This ensures nba_players_extended has the SAME players as nbaNew (no repeats),
with real height/weight from the API for proper physical-based matching.
"""
import os
import sys
import pandas as pd
import time
from pathlib import Path
from nba_api.stats.static import players as static_players
from nba_api.stats.endpoints import commonplayerinfo

BASE_DIR = Path(__file__).resolve().parent.parent
NBA_NEW_PATH = BASE_DIR / "app" / "ai" / "nbaNew.csv"
OUT_PATH = BASE_DIR / "app" / "ai" / "nba_players_extended.csv"


def get_player_physicals(name: str) -> tuple[float, float] | None:
    """Fetch height (inches) and weight (lbs) from nba_api. Returns (height, weight) or None."""
    try:
        matches = static_players.find_players_by_full_name(name)
        if not matches:
            return None
        pid = matches[0]["id"]
        info = commonplayerinfo.CommonPlayerInfo(player_id=pid).get_data_frames()[0].iloc[0]
        height_str = str(info.get("HEIGHT", "6-6"))
        weight = float(info.get("WEIGHT", 215))
        try:
            parts = height_str.replace("'", "-").split("-")
            ft = int(parts[0].strip())
            inches = int(parts[1].strip()) if len(parts) > 1 else 0
            height_inches = ft * 12 + inches
        except (ValueError, IndexError):
            height_inches = 78.0
        return (height_inches, weight)
    except Exception:
        return None


def main():
    if not NBA_NEW_PATH.exists():
        print(f"nbaNew.csv not found at {NBA_NEW_PATH}")
        return

    df = pd.read_csv(NBA_NEW_PATH)
    # Normalize column names (pandas may mangle %)
    df.columns = df.columns.str.strip()

    # Deduplicate by PlayerName - keep first occurrence (primary team/stats)
    df_unique = df.drop_duplicates(subset=["PlayerName"], keep="first").reset_index(drop=True)
    # Drop non-player rows (e.g. "League Average")
    df_unique = df_unique[~df_unique["PlayerName"].astype(str).str.lower().str.contains("league average|team total", na=False)]
    print(f"Loaded {len(df)} rows from nbaNew, {len(df_unique)} unique players")

    rows = []
    seen_names = set()
    failed = []

    for idx, row in df_unique.iterrows():
        name = str(row["PlayerName"]).strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Get stats from nbaNew
        pts = float(row["PTS"])
        trb = float(row["TRB"])
        ast = float(row["AST"])
        stl = float(row["STL"])
        blk = float(row["BLK"])
        team = str(row.get("Team", "NBA")).strip()
        pos = str(row.get("Pos", "G/F")).strip()
        def _f(cols, default):
            for c in cols:
                v = row.get(c)
                if v is not None and pd.notna(v) and str(v).strip() != "":
                    try: return float(v)
                    except (ValueError, TypeError): pass
            return default
        fg_pct = _f(["FG%", "FG_PCT"], 0.45)
        fg3_pct = _f(["3P%", "FG3_PCT"], 0.35)
        ft_pct = _f(["FT%", "FT_PCT"], 0.75)

        # Fetch height/weight from API
        physicals = get_player_physicals(name)
        if physicals:
            height_inches, weight_lbs = physicals
        else:
            height_inches, weight_lbs = 78.0, 215.0
            failed.append(name)

        rows.append({
            "PLAYER_NAME": name,
            "TEAM_ABBREVIATION": team,
            "POSITION": pos,
            "HEIGHT_INCHES": int(height_inches),
            "WEIGHT_LBS": int(weight_lbs),
            "PTS": pts,
            "REB": trb,
            "AST": ast,
            "STL": stl,
            "BLK": blk,
            "FG_PCT": fg_pct,
            "FG3_PCT": fg3_pct,
            "FT_PCT": ft_pct,
        })
        print(f"  [{len(rows)}] {name} ({height_inches:.0f}\", {weight_lbs:.0f} lbs)")
        time.sleep(0.25)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(OUT_PATH, index=False)
    print(f"\nSaved {len(out_df)} players to {OUT_PATH}")
    if failed:
        print(f"  (API height lookup failed for {len(failed)} players; used defaults)")


if __name__ == "__main__":
    main()
