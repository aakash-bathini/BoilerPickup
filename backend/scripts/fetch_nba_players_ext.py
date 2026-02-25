import os
import sys
import pandas as pd
import time
from pathlib import Path
from nba_api.stats.endpoints import leaguedashplayerstats, commonplayerinfo

# Root path config
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

OUT_PATH = BASE_DIR / "app" / "ai" / "nba_players_extended.csv"

def fetch_players():
    print("Fetching top 50 NBA players (2024-25) - FAST MODE...")
    try:
        stats = leaguedashplayerstats.LeagueDashPlayerStats(season='2024-25').get_data_frames()[0]
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return
    
    # Filter for active players, top 50 by minutes
    stats = stats.sort_values(by='MIN', ascending=False).head(50)
    
    physicals = []
    print(f"Fetching physicals for {len(stats)} players...")
    
    for idx, row in stats.iterrows():
        pid = row['PLAYER_ID']
        name = row['PLAYER_NAME']
        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=pid).get_data_frames()[0].iloc[0]
            height_str = info['HEIGHT']
            weight = info['WEIGHT']
            pos = info['POSITION']
            
            # Convert height to inches
            try:
                ft, inches = map(int, height_str.split('-'))
                height_inches = (ft * 12) + inches
            except:
                height_inches = 78.0
                
            physicals.append({
                'PLAYER_ID': pid,
                'HEIGHT_INCHES': height_inches,
                'WEIGHT_LBS': weight,
                'POSITION': pos
            })
            print(f"  [+] {name} ({height_str})")
            time.sleep(0.3) # Fast but not aggressive
        except Exception as e:
            print(f"  [!] Skipped {name}: {e}")
            
    phys_df = pd.DataFrame(physicals)
    final_df = stats.merge(phys_df, on='PLAYER_ID')
    
    # Save key columns
    cols_to_save = [
        'PLAYER_NAME', 'TEAM_ABBREVIATION', 'POSITION', 'HEIGHT_INCHES', 'WEIGHT_LBS',
        'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT', 'FT_PCT'
    ]
    final_df[cols_to_save].to_csv(OUT_PATH, index=False)
    print(f"DONE! Saved to {OUT_PATH}")

if __name__ == "__main__":
    fetch_players()
