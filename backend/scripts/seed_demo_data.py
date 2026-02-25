#!/usr/bin/env python3
"""
Seed demo data: users, games, challenges, messages, etc.
Enables model training and tests all app features.

Run from backend/: python scripts/seed_demo_data.py

Creates:
- 60 users (varied names, positions, heights, skills)
- 30+ completed team games with stats
- 20+ completed 1v1 challenges + pending/accepted
- DM messages (conversations)
- Game chat messages
- Open/full/in_progress games
- Skill rating backfill
"""
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import joinedload
from app.database import SessionLocal
from app.models import (
    User, Game, GameParticipant, PlayerGameStats,
    Challenge, SkillHistory, Message,
    StatsContest, GameReschedule,
)
from app.auth import hash_password

# Names for variety
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
    "Nikhil", "Marcus", "Jake", "Chris", "Derek", "Ethan", "Ryan",
    "Mike", "David", "James", "Kevin", "Brandon", "Tyler", "Zach", "Matt",
    "Sarah", "Emma", "Olivia", "Sophia", "Isabella", "Mia", "Chloe", "Lily",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker",
]
POSITIONS = ["PG", "SG", "SF", "PF", "C"]
HEIGHTS = ["5'8", "5'9", "5'10", "6'0", "6'1", "6'2", "6'3", "6'4", "6'5", "6'6", "6'7"]

DM_MESSAGES = [
    "Hey! Want to run some 1v1 later?",
    "Sure, I'm down. CoRec around 6?",
    "Perfect, see you there!",
    "Good game yesterday, we should team up again",
    "Yeah that was fun. You free for 5v5 tomorrow?",
    "Let's do it. I'll create the game",
    "You still coming to the game?",
    "Running 5 min late, be there soon",
    "No worries, we'll wait",
    "Nice shot! We got next",
    "GG, rematch?",
    "Next time for sure",
]
GAME_CHAT_MESSAGES = [
    "Who's bringing the ball?",
    "I got it",
    "Let's run it",
    "Good luck everyone",
    "GG all",
    "See you next week",
]


def _utcnow():
    return datetime.now(timezone.utc)


def create_users(db, n: int = 60) -> list[User]:
    """Create n users with varied attributes."""
    users = []
    used = set()
    for i in range(n):
        while True:
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            uname = f"{first.lower()}{last.lower()}{i}".replace(" ", "")[:20]
            if uname not in used:
                used.add(uname)
                break
        email = f"{uname}@purdue.edu"
        if db.query(User).filter(User.email == email).first():
            continue
        skill = round(random.uniform(3.0, 8.0), 1)
        u = User(
            email=email,
            username=uname,
            password_hash=hash_password("demo123"),
            display_name=f"{first} {last}",
            height=random.choice(HEIGHTS),
            weight=random.randint(160, 220) if random.random() > 0.3 else None,
            preferred_position=random.choice(POSITIONS),
            self_reported_skill=min(10, max(1, int(skill))),
            ai_skill_rating=skill,
            skill_confidence=round(random.uniform(0.2, 0.9), 2),
            games_played=0,
            wins=0,
            losses=0,
            challenge_wins=0,
            challenge_losses=0,
            email_verified=True,
        )
        db.add(u)
        users.append(u)
    db.commit()
    for u in users:
        db.refresh(u)
    return users


def create_completed_game(db, users: list[User], game_type: str, creator: User) -> Game:
    """Create a completed game with participants, stats, and updated user records."""
    max_players = {"5v5": 10, "3v3": 6, "2v2": 4}[game_type]
    n_per_team = max_players // 2
    pool = [u for u in users if u.id != creator.id]
    if len(pool) < max_players - 1:
        return None
    chosen = [creator] + random.sample(pool, max_players - 1)
    random.shuffle(chosen)
    team_a = chosen[:n_per_team]
    team_b = chosen[n_per_team:]

    scheduled = _utcnow() - timedelta(days=random.randint(1, 60))
    game = Game(
        creator_id=creator.id,
        game_type=game_type,
        scheduled_time=scheduled,
        skill_min=3.0,
        skill_max=8.0,
        status="completed",
        team_a_score=random.randint(10, 21),
        team_b_score=random.randint(8, 19),
        completed_at=scheduled + timedelta(hours=1),
        stats_finalized=True,
        stats_finalized_at=scheduled + timedelta(hours=1),
    )
    # Ensure different scores
    if game.team_a_score == game.team_b_score:
        game.team_a_score += 1
    db.add(game)
    db.flush()

    winning_team = "A" if game.team_a_score > game.team_b_score else "B"
    for p in team_a:
        gp = GameParticipant(user_id=p.id, game_id=game.id, team="A")
        db.add(gp)
        p.games_played += 1
        p.wins += 1 if winning_team == "A" else 0
        p.losses += 1 if winning_team != "A" else 0
        # Stats for 5v5 baseline
        base = {"5v5": (3, 2, 1), "3v3": (5, 3, 1), "2v2": (7, 4, 2)}[game_type]
        pts = max(0, int(random.gauss(base[0], 3)))
        reb = max(0, int(random.gauss(base[1], 2)))
        ast = max(0, int(random.gauss(base[2], 1)))
        fgm = pts  # simplified
        fga = max(fgm + 2, pts + random.randint(2, 8))
        db.add(PlayerGameStats(
            user_id=p.id, game_id=game.id,
            pts=pts, reb=reb, ast=ast, stl=random.randint(0, 3), blk=random.randint(0, 2),
            tov=random.randint(0, 3), fgm=fgm, fga=fga, three_pm=min(pts, random.randint(0, 3)),
            three_pa=random.randint(0, 5), ftm=random.randint(0, 4), fta=random.randint(0, 4),
        ))
    for p in team_b:
        gp = GameParticipant(user_id=p.id, game_id=game.id, team="B")
        db.add(gp)
        p.games_played += 1
        p.wins += 1 if winning_team == "B" else 0
        p.losses += 1 if winning_team != "B" else 0
        base = {"5v5": (3, 2, 1), "3v3": (5, 3, 1), "2v2": (7, 4, 2)}[game_type]
        pts = max(0, int(random.gauss(base[0], 3)))
        reb = max(0, int(random.gauss(base[1], 2)))
        ast = max(0, int(random.gauss(base[2], 1)))
        fgm = pts
        fga = max(fgm + 2, pts + random.randint(2, 8))
        db.add(PlayerGameStats(
            user_id=p.id, game_id=game.id,
            pts=pts, reb=reb, ast=ast, stl=random.randint(0, 3), blk=random.randint(0, 2),
            tov=random.randint(0, 3), fgm=fgm, fga=fga, three_pm=min(pts, random.randint(0, 3)),
            three_pa=random.randint(0, 5), ftm=random.randint(0, 4), fta=random.randint(0, 4),
        ))
    return game


def create_challenge(db, u1: User, u2: User) -> Challenge:
    """Create a completed 1v1 challenge."""
    if u1.id == u2.id:
        return None
    score_a = random.randint(10, 15)
    score_b = random.randint(8, 14)
    if score_a == score_b:
        score_a += 1
    winner = u1 if score_a > score_b else u2
    loser = u2 if winner.id == u1.id else u1
    c = Challenge(
        challenger_id=u1.id,
        challenged_id=u2.id,
        status="completed",
        challenger_score=score_a if u1.id == winner.id else score_b,
        challenged_score=score_b if u1.id == winner.id else score_a,
        challenger_confirmed=True,
        challenged_confirmed=True,
        winner_id=winner.id,
        completed_at=_utcnow() - timedelta(days=random.randint(1, 30)),
    )
    db.add(c)
    winner.challenge_wins += 1
    loser.challenge_losses += 1
    return c


def create_open_game(db, users: list[User], game_type: str, creator: User) -> Game:
    """Create an open or full game (not completed) for variety."""
    max_players = {"5v5": 10, "3v3": 6, "2v2": 4}[game_type]
    n_join = random.randint(0, max_players - 1)
    pool = [u for u in users if u.id != creator.id]
    chosen = [creator] + (random.sample(pool, min(n_join, len(pool))) if pool else [])
    scheduled = _utcnow() + timedelta(days=random.randint(1, 14))
    status = "full" if len(chosen) >= max_players else "open"
    game = Game(
        creator_id=creator.id,
        game_type=game_type,
        scheduled_time=scheduled,
        skill_min=3.0,
        skill_max=8.0,
        status=status,
        max_players=max_players,
    )
    db.add(game)
    db.flush()
    for i, p in enumerate(chosen):
        team = "A" if i % 2 == 0 else "B" if len(chosen) > 1 else "unassigned"
        if status == "full" and len(chosen) == max_players:
            team = "A" if i < max_players // 2 else "B"
        db.add(GameParticipant(user_id=p.id, game_id=game.id, team=team))
    return game


def create_dm_messages(db, users: list[User], n_conversations: int = 25, msgs_per_conv: int = 4) -> int:
    """Create DM conversations between users."""
    created = 0
    pairs = set()
    while len(pairs) < n_conversations:
        u1, u2 = random.sample(users, 2)
        key = tuple(sorted([u1.id, u2.id]))
        if key in pairs:
            continue
        pairs.add(key)
        for i in range(msgs_per_conv):
            sender, recipient = (u1, u2) if i % 2 == 0 else (u2, u1)
            content = random.choice(DM_MESSAGES)
            t = _utcnow() - timedelta(days=random.randint(0, 14), hours=random.randint(0, 23))
            msg = Message(
                sender_id=sender.id,
                game_id=None,
                recipient_id=recipient.id,
                content=content,
            )
            msg.created_at = t
            db.add(msg)
            created += 1
    return created


def create_game_messages(db, games: list[Game], users: list[User]) -> int:
    """Add chat messages to games (participants only)."""
    created = 0
    for game in random.sample(games, min(10, len(games))):
        participants = db.query(GameParticipant).filter(
            GameParticipant.game_id == game.id
        ).all()
        if not participants:
            continue
        for _ in range(random.randint(2, 5)):
            p = random.choice(participants)
            content = random.choice(GAME_CHAT_MESSAGES)
            t = (game.scheduled_time or _utcnow()) + timedelta(minutes=random.randint(-30, 60))
            msg = Message(
                sender_id=p.user_id,
                game_id=game.id,
                recipient_id=None,
                content=content,
            )
            msg.created_at = t
            db.add(msg)
            created += 1
    return created


def create_pending_challenges(db, users: list[User], n: int = 8) -> int:
    """Create pending, accepted, and in_progress challenges."""
    created = 0
    statuses = ["pending"] * 4 + ["accepted"] * 2 + ["in_progress"] * 2
    for i in range(n):
        u1, u2 = random.sample(users, 2)
        status = statuses[i % len(statuses)]
        c = Challenge(
            challenger_id=u1.id,
            challenged_id=u2.id,
            status=status,
            message="Let's run it at the CoRec!" if random.random() > 0.5 else None,
            scheduled_time=_utcnow() + timedelta(days=random.randint(1, 7)) if status != "pending" else None,
        )
        db.add(c)
        created += 1
    return created


def create_in_progress_game(db, users: list[User]) -> Game | None:
    """Create one in_progress game (full roster, no score yet)."""
    creator = random.choice(users)
    gt = "5v5"
    max_players = 10
    pool = [u for u in users if u.id != creator.id]
    if len(pool) < max_players - 1:
        return None
    chosen = [creator] + random.sample(pool, max_players - 1)
    game = Game(
        creator_id=creator.id,
        game_type=gt,
        scheduled_time=_utcnow() - timedelta(minutes=15),
        skill_min=3.0,
        skill_max=8.0,
        status="in_progress",
        max_players=max_players,
    )
    db.add(game)
    db.flush()
    for i, p in enumerate(chosen):
        team = "A" if i < 5 else "B"
        db.add(GameParticipant(user_id=p.id, game_id=game.id, team=team))
    return game


def create_stats_contest(db, games: list[Game], users: list[User]) -> int:
    """Create a stats contest on a completed game (within review period)."""
    completed = [g for g in games if g.status == "completed" and g.stats_finalized]
    if not completed:
        return 0
    game = random.choice(completed)
    participants = db.query(GameParticipant).filter(GameParticipant.game_id == game.id).all()
    if not participants:
        return 0
    contester = random.choice(participants).user
    c = StatsContest(
        game_id=game.id,
        contester_id=contester.id,
        reason="I had 5 assists, not 3. Check the scorekeeper.",
        status="open",
    )
    db.add(c)
    return 1


def create_reschedule_proposal(db, games: list[Game], users: list[User]) -> int:
    """Create a game reschedule proposal."""
    open_full = [g for g in games if g.status in ("open", "full") and g.scheduled_time]
    if not open_full:
        return 0
    game = random.choice(open_full)
    creator = db.query(User).filter(User.id == game.creator_id).first()
    if not creator:
        return 0
    r = GameReschedule(
        game_id=game.id,
        proposed_scheduled_time=game.scheduled_time + timedelta(days=1),
        proposed_by_id=creator.id,
        status="pending",
    )
    db.add(r)
    return 1


def backfill_skill_ratings(db) -> int:
    """Run update_ratings_after_game on all completed games (chronological order)."""
    from app.ai.rating import update_ratings_after_game
    games = (
        db.query(Game)
        .filter(Game.status == "completed")
        .order_by(Game.completed_at.asc().nullslast(), Game.scheduled_time.asc())
        .all()
    )
    for game in games:
        participants = (
            db.query(GameParticipant)
            .options(joinedload(GameParticipant.user))
            .filter(GameParticipant.game_id == game.id)
            .all()
        )
        if participants and all(p.user for p in participants):
            try:
                update_ratings_after_game(db, game, participants)
            except Exception:
                pass
    return len(games)


def main():
    db = SessionLocal()
    try:
        print("Seeding demo data...")
        existing = db.query(User).filter(User.is_disabled == False).all()
        if len(existing) < 50:
            n_create = 60 - len(existing)
            print(f"  Creating {n_create} users...")
            new_users = create_users(db, n_create)
            print(f"  Created {len(new_users)} users")
        users = db.query(User).filter(User.is_disabled == False).all()
        print(f"  Total users: {len(users)}")

        if len(users) < 10:
            print("  Need at least 10 users. Create more or run seed_e2e_user first.")
            return

        # Completed games
        completed = db.query(Game).filter(Game.status == "completed").count()
        target = 30
        if completed < target:
            print(f"  Creating {target - completed} completed games...")
            for _ in range(target - completed):
                creator = random.choice(users)
                gt = random.choice(["5v5", "3v3", "2v2"])
                create_completed_game(db, users, gt, creator)
            db.commit()
            completed = db.query(Game).filter(Game.status == "completed").count()
        print(f"  Completed games: {completed}")

        # 1v1 challenges
        challenges = db.query(Challenge).filter(Challenge.status == "completed").count()
        target_ch = 20
        if challenges < target_ch:
            print(f"  Creating {target_ch - challenges} completed 1v1 challenges...")
            for _ in range(target_ch - challenges):
                u1, u2 = random.sample(users, 2)
                create_challenge(db, u1, u2)
            db.commit()
            challenges = db.query(Challenge).filter(Challenge.status == "completed").count()
        print(f"  Completed 1v1 challenges: {challenges}")

        # Open/full games for variety
        open_count = db.query(Game).filter(Game.status.in_(["open", "full"])).count()
        if open_count < 8:
            print(f"  Creating {8 - open_count} open/full games...")
            for _ in range(8 - open_count):
                creator = random.choice(users)
                gt = random.choice(["5v5", "3v3", "2v2"])
                create_open_game(db, users, gt, creator)
            db.commit()
        print(f"  Open/full games: {db.query(Game).filter(Game.status.in_(['open', 'full'])).count()}")

        # In-progress game
        in_progress = db.query(Game).filter(Game.status == "in_progress").count()
        if in_progress < 1:
            print("  Creating 1 in-progress game...")
            create_in_progress_game(db, users)
            db.commit()
        print(f"  In-progress games: {db.query(Game).filter(Game.status == 'in_progress').count()}")

        # Pending/accepted challenges
        pending_ch = db.query(Challenge).filter(
            Challenge.status.in_(["pending", "accepted", "in_progress"])
        ).count()
        if pending_ch < 8:
            print(f"  Creating {8 - pending_ch} pending/accepted challenges...")
            create_pending_challenges(db, users, 8 - pending_ch)
            db.commit()

        # DM messages
        dm_count = db.query(Message).filter(Message.game_id.is_(None)).count()
        if dm_count < 50:
            print("  Creating DM conversations...")
            n = create_dm_messages(db, users, n_conversations=25, msgs_per_conv=4)
            db.commit()
            print(f"  DM messages: {db.query(Message).filter(Message.game_id.is_(None)).count()}")

        # Game chat messages
        game_msg_count = db.query(Message).filter(Message.game_id.isnot(None)).count()
        if game_msg_count < 20:
            print("  Creating game chat messages...")
            all_games = db.query(Game).all()
            create_game_messages(db, all_games, users)
            db.commit()
            print(f"  Game messages: {db.query(Message).filter(Message.game_id.isnot(None)).count()}")

        # Stats contest (dispute stats on a completed game)
        if db.query(StatsContest).count() < 1:
            print("  Creating stats contest...")
            all_games = db.query(Game).all()
            create_stats_contest(db, all_games, users)
            db.commit()

        # Reschedule proposal
        if db.query(GameReschedule).count() < 1:
            print("  Creating reschedule proposal...")
            all_games = db.query(Game).all()
            create_reschedule_proposal(db, all_games, users)
            db.commit()

        # Backfill skill ratings from completed games
        print("  Backfilling skill ratings...")
        backfill_skill_ratings(db)

        db.commit()
        print("\nDone! You can now:")
        print("  1. Train win predictor: curl -X POST http://localhost:8000/api/train-predictor")
        print("  2. Browse the app — users, games, challenges, leaderboard should be populated")
        print("  3. Login with any seeded user: <username>@purdue.edu / demo123")
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
