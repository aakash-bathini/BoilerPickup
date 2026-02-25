"""
Coach Pete — assistant for Boiler Pickup.

Uses external API when configured. Receives full context from the database:
user stats, 1v1 history, all players, and weather. Falls back to rule-based
engine when not configured.
"""
import os
import httpx
from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Response

from app.time_utils import now_est, to_est
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from sqlalchemy import or_

from app.database import get_db
from app.models import User, PlayerGameStats, Challenge, Game, GameParticipant, SkillHistory
from app.auth import get_current_user
from app.ai.player_match import find_matches, find_complementary_teammates

router = APIRouter(prefix="/api", tags=["assistant"])

WEST_LAFAYETTE_LAT = 40.4237
WEST_LAFAYETTE_LON = -86.9212
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    reply: str
    data: Optional[dict] = None


class WeatherResponse(BaseModel):
    current: dict
    forecast: list[dict]


def _get_weather() -> dict:
    """Fetch live weather from Open-Meteo. No caching — always fresh."""
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={WEST_LAFAYETTE_LAT}&longitude={WEST_LAFAYETTE_LON}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            f"weather_code,wind_speed_10m,precipitation"
            f"&daily=temperature_2m_max,temperature_2m_min,weather_code,"
            f"precipitation_probability_max,wind_speed_10m_max"
            f"&temperature_unit=fahrenheit&wind_speed_unit=mph"
            f"&timezone=America/New_York&forecast_days=8"
        )
        resp = httpx.get(url, timeout=8.0)
        return resp.json()
    except Exception:
        return {}


def _weather_code_to_desc(code: int) -> str:
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Icy fog", 51: "Light drizzle", 53: "Drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
        71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
        80: "Light showers", 81: "Showers", 82: "Heavy showers",
        85: "Light snow showers", 86: "Snow showers",
        95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm",
    }
    return mapping.get(code, "Unknown")


def _parse_weather_current(data: dict) -> dict:
    """Extract current weather from Open-Meteo response."""
    c = data.get("current", {})
    return {
        "temperature": c.get("temperature_2m"),
        "feels_like": c.get("apparent_temperature"),
        "humidity": c.get("relative_humidity_2m"),
        "wind_speed": c.get("wind_speed_10m"),
        "precipitation": c.get("precipitation"),
        "description": _weather_code_to_desc(c.get("weather_code", 0)),
        "weather_code": c.get("weather_code", 0),
    }


def _parse_forecast_day(data: dict, day_index: int) -> dict | None:
    """Extract forecast for a specific day (0=today, 1=tomorrow, etc)."""
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if day_index >= len(dates):
        return None
    return {
        "date": dates[day_index],
        "high": (daily.get("temperature_2m_max") or [None])[day_index] if day_index < len(daily.get("temperature_2m_max", [])) else None,
        "low": (daily.get("temperature_2m_min") or [None])[day_index] if day_index < len(daily.get("temperature_2m_min", [])) else None,
        "description": _weather_code_to_desc((daily.get("weather_code") or [0])[day_index]) if day_index < len(daily.get("weather_code", [])) else "Unknown",
        "precip_chance": (daily.get("precipitation_probability_max") or [0])[day_index] if day_index < len(daily.get("precipitation_probability_max", [])) else 0,
        "wind": (daily.get("wind_speed_10m_max") or [0])[day_index] if day_index < len(daily.get("wind_speed_10m_max", [])) else 0,
    }


@router.get("/weather", response_model=WeatherResponse)
def get_weather(response: Response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    data = _get_weather()
    if not data or "current" not in data:
        raise HTTPException(status_code=503, detail="Weather service unavailable")

    current_out = _parse_weather_current(data)
    daily = data.get("daily", {})

    forecast = []
    dates = daily.get("time", [])
    for i, d in enumerate(dates):
        forecast.append({
            "date": d,
            "high": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
            "low": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
            "description": _weather_code_to_desc(daily.get("weather_code", [0])[i]) if i < len(daily.get("weather_code", [])) else "Unknown",
            "precip_chance": daily.get("precipitation_probability_max", [0])[i] if i < len(daily.get("precipitation_probability_max", [])) else 0,
            "wind": daily.get("wind_speed_10m_max", [0])[i] if i < len(daily.get("wind_speed_10m_max", [])) else 0,
        })

    return WeatherResponse(current=current_out, forecast=forecast)


def _build_user_context(db: Session, user: User) -> str:
    stats = db.query(PlayerGameStats).filter(PlayerGameStats.user_id == user.id).all()
    n = len(stats)

    context = f"User: {user.display_name} (@{user.username})\n"
    context += f"Skill Rating: {user.ai_skill_rating:.1f}/10 (confidence: {user.skill_confidence:.0%})\n"
    context += f"Position: {user.preferred_position or 'Any'}\n"
    context += f"Height: {user.height or 'N/A'}, Weight: {user.weight or 'N/A'} lbs\n"
    context += f"Team Record: {user.wins}W-{user.losses}L ({user.games_played} games)\n"
    context += f"1v1 Record: {user.challenge_wins}W-{user.challenge_losses}L\n"
    total_w = user.wins + user.challenge_wins
    total_l = user.losses + user.challenge_losses
    context += f"Overall Record: {total_w}W-{total_l}L\n"

    if n > 0:
        ppg = sum(s.pts for s in stats) / n
        rpg = sum(s.reb for s in stats) / n
        apg = sum(s.ast for s in stats) / n
        spg = sum(s.stl for s in stats) / n
        bpg = sum(s.blk for s in stats) / n
        topg = sum(s.tov for s in stats) / n
        fga_t = sum(s.fga for s in stats)
        fgm_t = sum(s.fgm for s in stats)
        tpa_t = sum(s.three_pa for s in stats)
        tpm_t = sum(s.three_pm for s in stats)
        fta_t = sum(s.fta for s in stats)
        ftm_t = sum(s.ftm for s in stats)
        fg_pct = (fgm_t / fga_t * 100) if fga_t > 0 else 0
        tp_pct = (tpm_t / tpa_t * 100) if tpa_t > 0 else 0
        ft_pct = (ftm_t / fta_t * 100) if fta_t > 0 else 0

        context += f"\nCareer Averages ({n} games with stats):\n"
        context += f"  PPG: {ppg:.1f}, RPG: {rpg:.1f}, APG: {apg:.1f}\n"
        context += f"  SPG: {spg:.1f}, BPG: {bpg:.1f}, TOPG: {topg:.1f}\n"
        context += f"  FG%: {fg_pct:.1f}%, 3P%: {tp_pct:.1f}%, FT%: {ft_pct:.1f}%\n"

        # Strengths/weaknesses analysis
        strengths = []
        weaknesses = []
        if ppg >= 12: strengths.append("elite scorer")
        elif ppg >= 8: strengths.append("solid scorer")
        elif ppg < 5 and n >= 3: weaknesses.append("scoring")
        if rpg >= 6: strengths.append("strong rebounder")
        elif rpg < 3 and n >= 3: weaknesses.append("rebounding")
        if apg >= 4: strengths.append("great passer")
        if spg >= 2: strengths.append("ball hawk on D")
        if bpg >= 1.5: strengths.append("rim protector")
        if topg >= 4 and n >= 3: weaknesses.append("ball security (high turnovers)")
        if fg_pct < 35 and fga_t > 5: weaknesses.append("shooting efficiency")
        if fg_pct >= 50: strengths.append("efficient shooter")

        if strengths:
            context += f"  Strengths: {', '.join(strengths)}\n"
        if weaknesses:
            context += f"  Areas to improve: {', '.join(weaknesses)}\n"
    else:
        context += "\nNo game stats recorded yet — play your first team game to start tracking!\n"

    challenges = (
        db.query(Challenge)
        .filter(
            Challenge.status == "completed",
            or_(
                Challenge.challenger_id == user.id,
                Challenge.challenged_id == user.id,
            ),
        )
        .order_by(Challenge.completed_at.desc().nullslast())
        .limit(15)
        .all()
    )
    if challenges:
        context += "\nRecent 1v1 Results:\n"
        for c in challenges:
            opp = c.challenged if c.challenger_id == user.id else c.challenger
            opp_name = opp.display_name if opp else "Unknown"
            won = c.winner_id == user.id
            score = f"{c.challenger_score}-{c.challenged_score}" if c.challenger_score is not None else "?"
            context += f"  vs {opp_name}: {'Won' if won else 'Lost'} ({score})\n"
    else:
        context += "\nNo 1v1 challenges completed yet.\n"

    return context


def _build_players_on_fire(db: Session, limit: int = 10) -> str:
    """Players whose skill rating increased the most over the past 7 days."""
    from sqlalchemy import func
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    gain_subq = (
        db.query(
            SkillHistory.user_id,
            func.sum(SkillHistory.new_rating - SkillHistory.old_rating).label("gain"),
        )
        .filter(SkillHistory.timestamp >= week_ago)
        .group_by(SkillHistory.user_id)
        .subquery()
    )
    rows = (
        db.query(User, gain_subq.c.gain)
        .join(gain_subq, User.id == gain_subq.c.user_id)
        .filter(User.is_disabled == False)
        .filter(gain_subq.c.gain > 0)
        .order_by(gain_subq.c.gain.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return "No players with rating gains in the past week."
    lines = ["Players on Fire (fastest rising skill, past 7 days):"]
    for u, gain in rows:
        lines.append(f"  {u.display_name} (@{u.username}): +{float(gain):.1f} (now {u.ai_skill_rating:.1f})")
    return "\n".join(lines)


def _parse_date_in_message(msg: str, est_now: datetime) -> int | None:
    """Parse date from message (e.g. 'Feb 26', 'Feb 27th', 'weather on Feb 26') and return forecast day index (0=today)."""
    import re
    est = est_now
    months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
    m = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?", msg, re.I)
    if m:
        month_name, day = m.group(1).lower(), int(m.group(2))
        month = months.get(month_name[:3])
        if month and 1 <= day <= 31:
            try:
                from datetime import date
                target = date(est.year, month, day)
                today = est.date()
                delta = (target - today).days
                if 0 <= delta <= 7:
                    return delta
            except ValueError:
                pass
    return None


def _build_all_users_summary(db: Session, current_user_id: int) -> str:
    users = db.query(User).filter(User.is_disabled == False, User.id != current_user_id).limit(50).all()
    lines = []
    for u in users:
        stats = db.query(PlayerGameStats).filter(PlayerGameStats.user_id == u.id).all()
        n = len(stats)
        avg_line = ""
        if n > 0:
            ppg = sum(s.pts for s in stats) / n
            rpg = sum(s.reb for s in stats) / n
            apg = sum(s.ast for s in stats) / n
            spg = sum(s.stl for s in stats) / n
            bpg = sum(s.blk for s in stats) / n
            topg = sum(s.tov for s in stats) / n
            avg_line = f" | {ppg:.1f}ppg {rpg:.1f}rpg {apg:.1f}apg {spg:.1f}spg {bpg:.1f}bpg {topg:.1f}topg"

        lines.append(
            f"ID:{u.id} {u.display_name} (@{u.username}) "
            f"Skill:{u.ai_skill_rating:.1f} Pos:{u.preferred_position or '?'} "
            f"H:{u.height or '?'} W:{u.weight or '?'}lb "
            f"{u.wins}W-{u.losses}L ({u.games_played}gp){avg_line}"
        )
    return "\n".join(lines) if lines else "No other users registered yet."


def _format_game_time(dt: datetime) -> str:
    """Format datetime for EST display (West Lafayette)."""
    if dt is None:
        return "?"
    local = to_est(dt)
    return local.strftime("%a %b %d %I:%M %p EST")


def _build_games_context(db: Session, user: User) -> str:
    """Build context for user's upcoming and recent past games."""
    now = datetime.now(timezone.utc)

    participant_game_ids = (
        db.query(GameParticipant.game_id)
        .filter(GameParticipant.user_id == user.id)
        .subquery()
    )
    games = (
        db.query(Game)
        .filter(Game.id.in_(participant_game_ids))
        .order_by(Game.scheduled_time.desc())
        .limit(20)
        .all()
    )
    if not games:
        return "No team games (upcoming or recent)."

    upcoming = []
    past = []
    for g in games:
        st = g.scheduled_time
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        if st >= now:
            upcoming.append((g, st))
        else:
            past.append((g, st))

    lines = []
    if upcoming:
        lines.append("Upcoming games:")
        for g, st in sorted(upcoming, key=lambda x: x[1])[:10]:
            lines.append(f"  - {g.game_type} on {_format_game_time(st)} (status: {g.status})")
    if past:
        lines.append("Recent past games:")
        for g, st in past[:10]:
            score = f" {g.team_a_score}-{g.team_b_score}" if g.team_a_score is not None else ""
            lines.append(f"  - {g.game_type} on {_format_game_time(st)} (status: {g.status}{score})")
    return "\n".join(lines) if lines else "No team games (upcoming or recent)."


def _rule_based_reply(message: str, user_context: str, users_summary: str, weather_data: dict, user: User, db: Session, games_context: str = "") -> ChatResponse:
    msg = message.lower().strip()

    # Weather queries — detect "in X days", "tomorrow", "Feb 26", "Feb 27th"
    if any(w in msg for w in ["weather", "rain", "temperature", "outside", "cold", "hot", "walk", "corec", "snow", "wind", "forecast"]):
        if weather_data and "current" in weather_data:
            import re
            day_offset = None
            # Try explicit date first: "Feb 26", "Feb 27th", "weather on Feb 26"
            day_offset = _parse_date_in_message(msg, now_est())
            if day_offset is None:
                # "in 2 days", "in two days", "2 days from now", "tomorrow", "day after tomorrow"
                if "tomorrow" in msg and "day after" not in msg:
                    day_offset = 1
                elif "day after tomorrow" in msg or "in 2 days" in msg or "two days" in msg:
                    day_offset = 2
                elif "in 3 days" in msg or "three days" in msg:
                    day_offset = 3
                elif "in 4 days" in msg or "four days" in msg:
                    day_offset = 4
                elif "in 5 days" in msg or "five days" in msg:
                    day_offset = 5
                elif "in 6 days" in msg or "six days" in msg:
                    day_offset = 6
                elif "in 7 days" in msg or "week" in msg or "next week" in msg:
                    day_offset = min(7, 6)  # cap at index 6 for 7-day forecast
                else:
                    m = re.search(r"in\s+(\d+)\s+day", msg)
                    if m:
                        day_offset = min(int(m.group(1)), 7)

            if day_offset is not None and day_offset >= 1:
                f = _parse_forecast_day(weather_data, day_offset)
                if f:
                    high = f.get("high")
                    low = f.get("low")
                    desc = f.get("description", "Unknown")
                    precip = f.get("precip_chance", 0)
                    wind = f.get("wind", 0)
                    date_str = f.get("date", "")
                    day_label = "Tomorrow" if day_offset == 1 else (f"Day {day_offset}" if day_offset <= 7 else f"In {day_offset} days")
                    reply = f"**West Lafayette Weather {day_label}** ({date_str})\n\n"
                    reply += f"🌡 High **{high}°F** / Low **{low}°F**\n"
                    reply += f"☁️ {desc}\n"
                    reply += f"💨 Wind: {wind} mph | 🌧 {precip}% chance of rain\n\n"
                    if isinstance(high, (int, float)):
                        if high < 35:
                            reply += "🧊 Cold — layer up for the walk to the CoRec."
                        elif high < 55:
                            reply += "🧥 Chilly — bring a jacket."
                        elif high < 75:
                            reply += "👍 Nice conditions for ball at the CoRec."
                        else:
                            reply += "☀️ Warm — stay hydrated!"
                    return ChatResponse(reply=reply)

            # Default: current weather
            w = _parse_weather_current(weather_data)
            temp = w.get("temperature")
            feels = w.get("feels_like")
            desc = w.get("description", "Unknown")
            wind = w.get("wind_speed")
            humidity = w.get("humidity")

            reply = f"**West Lafayette Weather Right Now**\n\n"
            reply += f"🌡 **{temp}°F** (feels like {feels}°F)\n"
            reply += f"☁️ {desc}\n"
            reply += f"💨 Wind: {wind} mph | 💧 Humidity: {humidity}%\n\n"

            if isinstance(temp, (int, float)):
                if temp < 20:
                    reply += "🥶 It's brutally cold! Definitely drive to the CoRec or wait for a warmer day."
                elif temp < 35:
                    reply += "🧊 Below freezing. Layer up if you're walking to the CoRec — gloves and hat recommended."
                elif temp < 50:
                    reply += "🧥 Chilly but manageable. Grab a jacket for the walk to the CoRec."
                elif temp < 70:
                    reply += "👍 Perfect conditions for a walk to the CoRec. Enjoy the fresh air!"
                elif temp < 85:
                    reply += "☀️ Warm out! Light clothes and bring water to the CoRec."
                else:
                    reply += "🔥 It's hot! Stay hydrated. Bring extra water to the game."

            return ChatResponse(reply=reply)
        return ChatResponse(reply="I couldn't reach the weather service right now. Try again in a moment!")

    # Find match (similar players) — returns data for popup
    if any(w in msg for w in ["find a match", "find match", "match me", "who should i play", "find someone like me", "similar player", "my match"]):
        matches = find_matches(db, user.id, limit=5, skill_tolerance=1.5)
        if matches:
            reply = "🎯 **I found players similar to you.** Challenge them to 1v1 or message below!"
            data = {
                "matched_players": [
                    {"id": m.id, "display_name": m.display_name, "username": m.username, "ai_skill_rating": m.ai_skill_rating}
                    for m in matches
                ],
                "match_type": "similar",
            }
            return ChatResponse(reply=reply, data=data)
        return ChatResponse(reply="No similar players found yet. Invite friends to join!")

    # Find teammate (complementary skills) — returns data for popup
    if any(w in msg for w in ["find me a teammate", "find teammate", "teammate", "partner", "team up", "complement", "who complements"]):
        teammates = find_complementary_teammates(db, user.id, limit=5, skill_tolerance=1.5)
        if teammates:
            reply = "🤝 **Players who complement your skills.** Message them to team up!"
            data = {
                "matched_players": [
                    {"id": t.id, "display_name": t.display_name, "username": t.username, "ai_skill_rating": t.ai_skill_rating}
                    for t in teammates
                ],
                "match_type": "teammate",
            }
            return ChatResponse(reply=reply, data=data)
        return ChatResponse(reply="No complementary players found yet. Invite friends to join!")

    # Players on Fire — fastest rising skill over past week
    if any(w in msg for w in ["players on fire", "who's hot", "who is hot", "fastest rising", "rising stars", "hot this week", "on fire"]):
        fire = _build_players_on_fire(db)
        if "No players" in fire:
            return ChatResponse(reply="No one has gained skill rating in the past week. Play games and win to climb!")
        reply = "🔥 **Players on Fire** (fastest rising skill, past 7 days):\n\n" + fire.replace("Players on Fire (fastest rising skill, past 7 days):\n  ", "").replace("\n  ", "\n• ")
        reply += "\n\nCheck the Rankings page and filter by \"Players on Fire\" to see the full list!"
        return ChatResponse(reply=reply)

    # Teammate/player search queries (generic — no popup)
    if any(w in msg for w in ["recommend", "find player", "who should", "need a", "good at", "rebound", "steal", "scorer", "assist", "block", "tall", "height"]):
        lines = users_summary.split("\n")
        if lines and lines[0] == "No other users registered yet.":
            return ChatResponse(reply="No other players are registered yet. Invite your friends to join Boiler Pickup!")

        # Try to match specific queries
        filtered = lines
        if "rebound" in msg or "board" in msg:
            filtered = [l for l in lines if "rpg" in l and float(l.split("rpg")[0].split()[-1]) >= 4] or lines
            reply = "🏀 **Top Rebounders Available:**\n\n"
        elif "steal" in msg or "defense" in msg or "defensive" in msg:
            filtered = [l for l in lines if "spg" in l and float(l.split("spg")[0].split()[-1]) >= 1.5] or lines
            reply = "🔒 **Defensive Specialists:**\n\n"
        elif "scor" in msg or "point" in msg or "bucket" in msg:
            filtered = [l for l in lines if "ppg" in l and float(l.split("ppg")[0].split()[-1]) >= 8] or lines
            reply = "🎯 **Top Scorers Available:**\n\n"
        elif "pass" in msg or "assist" in msg:
            filtered = [l for l in lines if "apg" in l and float(l.split("apg")[0].split()[-1]) >= 3] or lines
            reply = "🎯 **Best Passers:**\n\n"
        elif "tall" in msg or "height" in msg or "big" in msg:
            filtered = [l for l in lines if "6'" in l or "6'" in l] or lines
            reply = "📏 **Tallest Players:**\n\n"
        else:
            reply = "🏀 **Available Players:**\n\n"

        for line in filtered[:8]:
            reply += f"• {line}\n"
        reply += "\nVisit their profiles to send a message or challenge them to a 1v1!"
        return ChatResponse(reply=reply)

    # Stats and performance queries
    if any(w in msg for w in ["my stats", "my rating", "my record", "how am i", "my performance", "my average", "my game"]):
        reply = f"📊 **Your Profile:**\n\n{user_context}"
        return ChatResponse(reply=reply)

    # 1v1 advice — check before "improve" so "1v1 tips" doesn't match "tip"
    if any(w in msg for w in ["1v1", "challenge", "versus", "opponent", "duel"]):
        reply = "⚡ **1v1 Guide:**\n\n"
        reply += "• Games are to **15 points**\n"
        reply += "• Both players must **confirm the score** for it to count\n"
        reply += "• Wins and losses affect your **skill rating** (Elo-style)\n"
        reply += "• Beating a higher-rated opponent gives a bigger rating boost\n"
        reply += "• Score margin matters — a 15-0 win is worth more than 15-14\n\n"
        reply += "**Tips for winning 1v1:**\n"
        reply += "• Use jab steps to create space\n"
        reply += "• Mix up your attack — don't be predictable\n"
        reply += "• Play solid on-ball defense and contest every shot\n"
        reply += "• If they're bigger, use speed. If they're faster, use strength.\n\n"
        reply += "Visit a player's profile or check the Leaderboard to issue a challenge!"
        return ChatResponse(reply=reply)

    # Improvement advice
    if any(w in msg for w in ["improve", "better", "tip", "advice", "train", "practice", "get good", "level up", "weakness"]):
        stats = db.query(PlayerGameStats).filter(PlayerGameStats.user_id == user.id).all()
        n = len(stats)

        reply = f"🏋️ **Coaching Tips for {user.display_name}:**\n\n"

        if n == 0:
            reply += "You haven't played any team games with stats yet! Here's general advice:\n\n"
            reply += "• **Shooting**: Practice catch-and-shoot from mid-range and 3-point line\n"
            reply += "• **Ball handling**: Work on crossovers and behind-the-back dribbles\n"
            reply += "• **Defense**: Stay in a low stance, watch the ball handler's hips not the ball\n"
            reply += "• **Rebounding**: Box out every time — position beats height\n"
            reply += "• **Court vision**: Always know where all 4 teammates are"
        else:
            ppg = sum(s.pts for s in stats) / n
            rpg = sum(s.reb for s in stats) / n
            apg = sum(s.ast for s in stats) / n
            topg = sum(s.tov for s in stats) / n
            fga_t = sum(s.fga for s in stats)
            fgm_t = sum(s.fgm for s in stats)
            fg_pct = (fgm_t / fga_t * 100) if fga_t > 0 else 0

            reply += f"Based on your averages ({ppg:.1f}ppg, {rpg:.1f}rpg, {apg:.1f}apg, {topg:.1f}topg, {fg_pct:.0f}% FG):\n\n"

            if fg_pct < 40 and fga_t > 5:
                reply += "• 🎯 **Shooting efficiency ({:.0f}%)** is below average. Focus on shot selection — take higher-percentage shots closer to the basket and only shoot 3s when you're wide open.\n".format(fg_pct)
            if topg > 3:
                reply += "• 🤦 **{:.1f} turnovers/game** is too many. Slow down, make the simple pass, and protect the ball in traffic.\n".format(topg)
            if rpg < 3:
                reply += "• 🏀 **Rebounding ({:.1f}/game)** — try to crash the boards harder. Box out your man on every shot attempt.\n".format(rpg)
            if apg < 2:
                reply += "• 👀 **Passing ({:.1f} ast/game)** — look for the open man more. Extra passes lead to better shots.\n".format(apg)
            if ppg < 5:
                reply += "• 💪 **Scoring** — be more aggressive looking for your shot. Set screens and cut to the basket.\n"

            if fg_pct >= 50 and ppg >= 10:
                reply += "• 🔥 You're playing great! Keep up the efficiency. Consider mentoring newer players.\n"

            reply += "\n**General pickup tips**: communicate on defense, call your screens, and hustle back on transition."

        return ChatResponse(reply=reply)

    # Upcoming/past games
    if any(w in msg for w in ["what games", "upcoming", "this week", "next week", "last week", "games i have", "my games", "when do i play", "schedule"]):
        if games_context:
            reply = "🏀 **Your Games:**\n\n" + games_context
            reply += "\n\nCheck the Games page for full details and to join more!"
            return ChatResponse(reply=reply)
        return ChatResponse(reply="You don't have any team games coming up or in recent history. Browse games or create one to get on the court!")

    # Game/app help
    if any(w in msg for w in ["how do", "how to", "help", "what can", "feature", "app", "guide", "tutorial"]):
        reply = "📱 **Boiler Pickup Guide:**\n\n"
        reply += "• **Create a game** — Set game type (2v2/3v3/5v5), time, and skill range\n"
        reply += "• **Join a game** — Browse games matched to your skill level\n"
        reply += "• **1v1 Challenges** — Challenge anyone from their profile page\n"
        reply += "• **Scorekeeper** — Invite a non-player to track live stats\n"
        reply += "• **Stats Contest** — Dispute stats within 24 hours of game completion\n"
        reply += "• **Messages** — DM any player or chat within a game lobby\n"
        reply += "• **Coach Pete (me!)** — Ask about teammates, stats, weather, tips\n\n"
        reply += "All games are at the **Purdue CoRec** (France A. Córdova Rec Center)."
        return ChatResponse(reply=reply)

    # Greetings and general conversation
    if any(w in msg for w in ["hello", "hi", "hey", "what's up", "sup", "yo", "how are", "good morning", "good evening"]):
        name = user.display_name.split()[0]
        reply = f"Hey {name}! 👋 I'm doing great, thanks for asking. "
        if user.games_played > 0:
            reply += f"I see you've got a {user.ai_skill_rating:.1f} skill rating — "
            if user.ai_skill_rating >= 7:
                reply += "you're killing it out there! "
            elif user.ai_skill_rating >= 5:
                reply += "solid player, keep grinding! "
            else:
                reply += "keep playing and you'll level up fast! "
        reply += "What can I help you with today?"
        return ChatResponse(reply=reply)

    # Compliments/thanks
    if any(w in msg for w in ["thanks", "thank you", "appreciate", "great", "awesome", "cool", "nice"]):
        return ChatResponse(reply="Happy to help! Let me know anytime you need advice, want to check the weather, or need help finding a teammate. 🏀")

    # Compare / win probability vs specific player
    if any(w in msg for w in ["compare", "win prob", "win probability", "chance to beat", "how do i stack", "vs ", " versus "]):
        import re
        from app.ai.win_predictor import predict_1v1_win_probability, calculate_betting_lines
        # Extract name
        name = None
        for pat in [r"compare\s+(?:me\s+)?to\s+@?(\w+)", r"vs\s+@?(\w+)", r"versus\s+@?(\w+)", r"against\s+@?(\w+)", r"win\s+prob(?:ability)?\s+(?:vs\s+)?@?(\w+)", r"chance\s+to\s+beat\s+@?(\w+)", r"how\s+do\s+i\s+compare\s+to\s+@?(\w+)"]:
            m = re.search(pat, msg, re.I)
            if m:
                name = m.group(1).strip()
                break
        if name and len(name) >= 2:
            other = db.query(User).filter(User.is_disabled == False, User.id != user.id).filter(
                or_(User.username.ilike(f"%{name}%"), User.display_name.ilike(f"%{name}%"))
            ).first()
            if other:
                my_win = predict_1v1_win_probability(user.ai_skill_rating, other.ai_skill_rating)
                lines = calculate_betting_lines(my_win)
                ml = lines["moneyline"]
                spread = lines["spread"]
                
                reply = f"📊 **Matchup Analysis: You vs {other.display_name}**\n\n"
                reply += f"Vegas estimates this as a **{spread} spread** with you at **{ml} moneyline**.\n\n"
                reply += f"• **Win Probability**: {(my_win * 100):.0f}%\n"
                reply += f"• **Rating Delta**: {(user.ai_skill_rating - other.ai_skill_rating):+.1f}\n\n"
                
                if my_win >= 0.6:
                    reply += f"You're the clear **favorite**! Don't get complacent. 🏀"
                elif my_win <= 0.4:
                    reply += f"You're the **underdog** (+{spread}), but your 'Hot Week' momentum suggests an upset is possible! 💪"
                else:
                    reply += "This is a **pick 'em** matchup. Every possession counts! 🔥"
                return ChatResponse(reply=reply, data={"compare_target": {"id": other.id, "display_name": other.display_name, "my_win_probability": round(my_win, 2), "moneyline": ml, "spread": spread}})
        return ChatResponse(reply="Who would you like to compare to? Try: \"Compare me to @username\" or \"Win probability vs John\"")

    # "Did I beat X recently?" — use challenge history from user_context
    if any(w in msg for w in ["beat", "beat me", "did i win", "did i lose", "recently", "last game", "last 1v1"]):
        challenges = (
            db.query(Challenge)
            .filter(
                Challenge.status == "completed",
                or_(
                    Challenge.challenger_id == user.id,
                    Challenge.challenged_id == user.id,
                ),
            )
            .order_by(Challenge.completed_at.desc().nullslast())
            .limit(10)
            .all()
        )
        if not challenges:
            return ChatResponse(reply="You haven't completed any 1v1 challenges yet. Challenge someone from their profile to get started!")
        users_list = db.query(User).filter(User.is_disabled == False).all()
        opp_name_lower = None
        for u in users_list:
            if u.id != user.id and (u.display_name.lower() in msg or u.username.lower() in msg):
                opp_name_lower = u.display_name.lower()
                break
        if opp_name_lower:
            for c in challenges:
                opp = c.challenged if c.challenger_id == user.id else c.challenger
                if opp and (opp.display_name.lower() == opp_name_lower or opp.username.lower() in msg):
                    won = c.winner_id == user.id
                    score = f"{c.challenger_score}-{c.challenged_score}" if c.challenger_score else "?"
                    if won:
                        return ChatResponse(reply=f"Yes! You beat {opp.display_name} in your last 1v1 ({score}). Nice win! 🏀")
                    return ChatResponse(reply=f"No — {opp.display_name} won your last 1v1 ({score}). Time for a rematch? 💪")
        last = challenges[0]
        opp = last.challenged if last.challenger_id == user.id else last.challenger
        won = last.winner_id == user.id
        score = f"{last.challenger_score}-{last.challenged_score}" if last.challenger_score else "?"
        reply = f"Your most recent 1v1 was vs {opp.display_name if opp else 'Unknown'}: "
        reply += f"{'You won' if won else 'You lost'} ({score})."
        return ChatResponse(reply=reply)

    # Smart default — avoid boilerplate when we can infer intent
    name = user.display_name.split()[0]
    # If they asked something weather-adjacent but we didn't match, offer forecast
    if any(w in msg for w in ["day", "week", "tomorrow", "when", "date"]):
        if weather_data and "daily" in weather_data:
            f1 = _parse_forecast_day(weather_data, 1)
            if f1:
                reply = f"Hey {name}! For **tomorrow** ({f1.get('date')}): high {f1.get('high')}°F, low {f1.get('low')}°F, {f1.get('description')}. "
                reply += "Ask \"weather in 3 days\" for other dates!"
                return ChatResponse(reply=reply)
    # Minimal fallback — only show full menu if truly unclear
    reply = f"Hey {name}! Try: **\"My stats\"**, **\"Find a match\"**, **\"Weather in 2 days\"**, or **\"How can I improve?\"** — I've got you! 🏀"
    return ChatResponse(reply=reply)


@router.post("/chat", response_model=ChatResponse)
async def coach_pete_chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_context = _build_user_context(db, current_user)
    users_summary = _build_all_users_summary(db, current_user.id)
    games_context = _build_games_context(db, current_user)

    # Always try to fetch weather for context
    weather_data = _get_weather()

    msg_lower = data.message.lower().strip()

    # Rule-based first for high-value intents — guarantees correct responses (external API can return generic greetings)
    rule_handled = [
        "find a match", "find match", "match me", "find me a teammate", "find teammate", "teammate",
        "my stats", "my rating", "my record",
        "weather", "rain", "temperature", "forecast", "tomorrow", "corec",
        "how can i improve", "improve", "how to improve",
        "compare", "vs ", "versus", "win prob", "chance to beat",
        "players on fire", "who's hot",
        "1v1", "challenge", "versus",
    ]
    if any(w in msg_lower for w in rule_handled):
        rule_result = _rule_based_reply(data.message, user_context, users_summary, weather_data, current_user, db, games_context)
        return rule_result

    current_datetime_str = now_est().strftime("%A, %B %d, %Y at %I:%M %p EST")

    # Structured prompt with grounding, guardrails, and few-shot guidance
    system_prompt = (
        "# ROLE & SCOPE\n"
        "You are Coach Pete, the expert AI assistant for Boiler Pickup at Purdue CoRec.\n"
        "You are a professional, high-energy basketball strategist with deep knowledge of Purdue hoops.\n\n"
        "# STRICT GUARDRAILS\n"
        "- ONLY discuss Boiler Pickup features, basketball strategy, user stats, weather, and matchmaking.\n"
        "- NEVER hallucinate data. If you don't see it in CONTEXT, say 'I don't have that data yet.'\n"
        "- Maintain a premium, grad-level tone. No juvenile AI speak.\n\n"
        "# INTELLIGENCE & MATCHMAKING\n"
        "- **1v1 Predictions:** When asked 'Can I beat X?' or 'Who should I play?', proactively use win probabilities.\n"
        "- **Betting Aesthetics:** Use Vegas terminology (Spread, Moneyline, Underdog) to describe matchups.\n"
        "  - e.g., 'You're a -4.5 favorite against Nikhil.' or 'The spread is tight (+1.5) for this 3v3.'\n"
        "- **Playstyle Fingerprints:** Reference NBA comparisons (e.g., 'You play like a young Mikal Bridges').\n"
        "- **Temporal Context:** Prioritize 'Hot Streak' and 'Weekly Wins' over lifetime totals when evaluating momentum.\n\n"
        "# GROUNDING RULES\n"
        "- Weather: Only for CoRec location. Indoor play is typical, but mentions heat/travel.\n"
        "- Player Lookup: If asked for 'best player', look at the HIGHEST skill rating in ALL REGISTERED PLAYERS.\n"
        "- Scheduling: Use 'USER'S TEAM GAMES'. Interpret 'this week' using CURRENT DATE.\n\n"
        "# FEW-SHOT EXAMPLES\n"
        "User: Can I beat Nikhil?\n"
        "Coach: [Check Win Predictor / Ratings] → 'It’s a toss-up! You’re currently a **+2.5 underdog** with a **42% win probability**. Focus on your rebounding to close the gap.'\n\n"
        "User: Who's on fire right now?\n"
        "Coach: [Check PLAYERS ON FIRE] → '**[Name]** is cooking with a **+[X]** skill jump this week! Visit the leaderboard to challenge them.'\n\n"
        "User: How's my game look?\n"
        "Coach: [Check NBA comparison] → 'Your game is looking sharp—very similar to **[NBA Match]** with that **[Similarity]%** match. Your passing (APG) is at a season high!'\n\n"
        "# CONTEXT\n"
        f"CURRENT DATE/TIME: {current_datetime_str}\n\n"
        f"## USER PROFILE\n{user_context}\n\n"
        f"## USER'S TEAM GAMES (upcoming and recent)\n{games_context}\n\n"
        f"## ALL REGISTERED PLAYERS\n{users_summary}\n\n"
        f"## PLAYERS ON FIRE (fastest rising skill, past 7 days)\n{_build_players_on_fire(db)}\n"
    )
    if weather_data and "current" in weather_data:
        w = _parse_weather_current(weather_data)
        system_prompt += (
            f"\n## WEATHER (West Lafayette, IN)\n"
            f"Current: {w.get('temperature')}°F (feels like {w.get('feels_like')}°F), "
            f"{w.get('description')}, Wind: {w.get('wind_speed')} mph, Humidity: {w.get('humidity')}%\n"
        )
        daily = weather_data.get("daily", {})
        dates = daily.get("time", [])
        if dates:
            system_prompt += "7-day forecast (Day 0=today, 1=tomorrow, etc.):\n"
            for i, d in enumerate(dates[:7]):
                f = _parse_forecast_day(weather_data, i)
                if f:
                    system_prompt += f"  Day {i} ({d}): high {f.get('high')}°F, low {f.get('low')}°F, {f.get('description')}, {f.get('precip_chance')}% precip\n"
        system_prompt += (
            "\nFor weather: use the forecast above for future dates. "
            "Current = right now. For \"weather in X days\", \"tomorrow\", \"weather on Feb 26\", \"Feb 27th\" — "
            "match the exact date from the forecast. NEVER guess temps. Use the exact day's high/low from the forecast.\n"
        )

    if GEMINI_API_KEY:
        try:
            import google.generativeai as genai
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                [system_prompt, data.message],
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=400,
                    temperature=0.4,
                    top_p=0.9,
                    top_k=40,
                ),
            )
            if response and response.text:
                return ChatResponse(reply=response.text.strip())
        except Exception:
            pass

    return _rule_based_reply(data.message, user_context, users_summary, weather_data, current_user, db, games_context)
