#!/usr/bin/env python3
"""
Seed demo data: users, games, challenges, messages, etc.
Enables model training and tests all app features.

Run from backend/: python scripts/seed_demo_data.py

Creates:
- 120 users with skill ratings spread 1.0–10.0 (elite to beginner)
- 25+ team games per user (high confidence: ~98%+)
- ~8 1v1 challenges per user
- 400+ completed team games total (for win predictor training)
- 80+ DM conversations, 400+ game chat messages
- Open/full/in_progress games, stats contests, reschedule proposals
- Skill rating backfill for leaderboard and model training
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

# Configuration
NUM_USERS = 120
MIN_TEAM_GAMES_PER_USER = 25  # Target for high confidence (1-exp(-25/6) ~ 98%)
MIN_CHALLENGES_PER_USER = 8   # 1v1 challenges per user for total_games boost
NUM_COMPLETED_GAMES = 60      # Base games before fill-up pass
NUM_COMPLETED_CHALLENGES = 960  # 120 * 8
NUM_PENDING_CHALLENGES = 30
NUM_OPEN_FULL_GAMES = 15
NUM_IN_PROGRESS_GAMES = 2
NUM_DM_CONVERSATIONS = 80
MSG_PER_DM_CONV = 6
NUM_GAMES_WITH_CHAT = 50
MSG_PER_GAME_CHAT = (3, 8)
NUM_STATS_CONTESTS = 5
NUM_RESCHEDULE_PROPOSALS = 5

# Skill distribution: ensure full 1–10 spread for testing
# (count, min_skill, max_skill) — creates users across the full range
SKILL_BUCKETS = [
    (4, 1.0, 1.5),   # Very low (1–1.5)
    (6, 1.5, 2.5),   # Low
    (10, 2.5, 3.5),  # Below average
    (15, 3.5, 4.5),  # Slightly below
    (25, 4.5, 5.5),  # Average (largest group)
    (25, 5.5, 6.5),  # Above average
    (15, 6.5, 7.5),  # Good
    (10, 7.5, 8.5),  # Very good
    (6, 8.5, 9.5),   # Elite
    (4, 9.5, 10.0),  # Top tier
]

FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
    "Nikhil", "Marcus", "Jake", "Chris", "Derek", "Ethan", "Ryan", "Cole", "Blake",
    "Mike", "David", "James", "Kevin", "Brandon", "Tyler", "Zach", "Matt", "Luke",
    "Sarah", "Emma", "Olivia", "Sophia", "Isabella", "Mia", "Chloe", "Lily", "Grace",
    "Noah", "Liam", "Mason", "Logan", "Hunter", "Carter", "Owen", "Connor",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker",
    "Hall", "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green", "Adams",
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
    "Who else is playing?",
    "I'll bring a ball",
    "Court 3 work for you?",
    "Down for 3v3 if we get one more",
]

GAME_CHAT_MESSAGES = [
    "Who's bringing the ball?",
    "I got it",
    "Let's run it",
    "Good luck everyone",
    "GG all",
    "See you next week",
    "Subs on the sideline",
    "Next bucket wins",
    "Let's go team",
    "Lock in",
]


def _utcnow():
    return datetime.now(timezone.utc)


def _skill_for_bucket(bucket_idx: int) -> float:
    """Return a random skill in the given bucket's range."""
    count, lo, hi = SKILL_BUCKETS[bucket_idx]
    return round(random.uniform(lo, hi), 1)


def create_users(db, n: int = NUM_USERS) -> list[User]:
    """Create n users with skill ratings spread 1.0–10.0."""
    users = []
    used = set()
    bucket_users = []
    for bucket_idx, (count, lo, hi) in enumerate(SKILL_BUCKETS):
        for _ in range(count):
            bucket_users.append(bucket_idx)
    random.shuffle(bucket_users)

    for i, bucket_idx in enumerate(bucket_users):
        if len(users) >= n:
            break
        for _ in range(10):  # Retry for unique username
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            suffix = f"{i:04d}{random.randint(100, 999)}"
            uname = f"{first.lower()}{last.lower()}{suffix}".replace(" ", "")[:20]
            if uname not in used:
                used.add(uname)
                break
        else:
            continue
        email = f"{uname}@purdue.edu"
        if db.query(User).filter(User.email == email).first():
            continue

        skill = _skill_for_bucket(bucket_idx)
        skill = min(10.0, max(1.0, skill))

        u = User(
            email=email,
            username=uname,
            password_hash=hash_password("demo123"),
            display_name=f"{first} {last}",
            height=random.choice(HEIGHTS),
            weight=random.randint(160, 220) if random.random() > 0.3 else None,
            preferred_position=random.choice(POSITIONS),
            self_reported_skill=min(10, max(1, int(round(skill)))),
            ai_skill_rating=skill,
            skill_confidence=round(random.uniform(0.3, 0.95), 2),
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


def _pool_by_skill(users: list[User], skill_min: float, skill_max: float, exclude_ids: set) -> list[User]:
    """Return users in skill range, excluding given IDs."""
    return [
        u for u in users
        if u.id not in exclude_ids
        and skill_min <= (u.ai_skill_rating or 5.0) <= skill_max
    ]


def create_completed_game(db, users: list[User], game_type: str, creator: User) -> Game | None:
    """Create a completed game with participants, stats, and updated user records."""
    max_players = {"5v5": 10, "3v3": 6, "2v2": 4}[game_type]
    n_per_team = max_players // 2

    # Use a skill band that includes creator
    cr_skill = creator.ai_skill_rating or 5.0
    band = 2.0
    skill_min = max(1.0, cr_skill - band)
    skill_max = min(10.0, cr_skill + band)

    pool = _pool_by_skill(users, skill_min, skill_max, {creator.id})
    if len(pool) < max_players - 1:
        pool = [u for u in users if u.id != creator.id]
    if len(pool) < max_players - 1:
        return None

    chosen = [creator] + random.sample(pool, max_players - 1)
    random.shuffle(chosen)
    team_a = chosen[:n_per_team]
    team_b = chosen[n_per_team:]

    scheduled = _utcnow() - timedelta(days=random.randint(1, 90))
    game = Game(
        creator_id=creator.id,
        game_type=game_type,
        scheduled_time=scheduled,
        skill_min=skill_min,
        skill_max=skill_max,
        status="completed",
        team_a_score=random.randint(10, 21),
        team_b_score=random.randint(8, 19),
        completed_at=scheduled + timedelta(hours=1),
        stats_finalized=True,
        stats_finalized_at=scheduled + timedelta(hours=1),
    )
    if game.team_a_score == game.team_b_score:
        game.team_a_score += 1
    db.add(game)
    db.flush()

    winning_team = "A" if game.team_a_score > game.team_b_score else "B"
    base = {"5v5": (3, 2, 1), "3v3": (5, 3, 1), "2v2": (7, 4, 2)}[game_type]

    for p in team_a:
        gp = GameParticipant(user_id=p.id, game_id=game.id, team="A")
        db.add(gp)
        p.games_played += 1
        p.wins += 1 if winning_team == "A" else 0
        p.losses += 1 if winning_team != "A" else 0
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

    for p in team_b:
        gp = GameParticipant(user_id=p.id, game_id=game.id, team="B")
        db.add(gp)
        p.games_played += 1
        p.wins += 1 if winning_team == "B" else 0
        p.losses += 1 if winning_team != "B" else 0
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


def create_challenge(db, u1: User, u2: User) -> Challenge | None:
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
        completed_at=_utcnow() - timedelta(days=random.randint(1, 45)),
    )
    db.add(c)
    winner.challenge_wins += 1
    loser.challenge_losses += 1
    return c


def create_open_game(db, users: list[User], game_type: str, creator: User) -> Game | None:
    """Create an open or full game (not completed)."""
    max_players = {"5v5": 10, "3v3": 6, "2v2": 4}[game_type]
    cr_skill = creator.ai_skill_rating or 5.0
    skill_min = max(1.0, cr_skill - 2.0)
    skill_max = min(10.0, cr_skill + 2.0)

    pool = _pool_by_skill(users, skill_min, skill_max, {creator.id})
    n_join = random.randint(0, min(max_players - 1, len(pool)))
    chosen = [creator] + (random.sample(pool, n_join) if pool and n_join > 0 else [])

    scheduled = _utcnow() + timedelta(days=random.randint(1, 21), hours=random.randint(0, 12))
    status = "full" if len(chosen) >= max_players else "open"
    game = Game(
        creator_id=creator.id,
        game_type=game_type,
        scheduled_time=scheduled,
        skill_min=skill_min,
        skill_max=skill_max,
        status=status,
        max_players=max_players,
    )
    db.add(game)
    db.flush()
    for i, p in enumerate(chosen):
        if status == "full" and len(chosen) == max_players:
            team = "A" if i < max_players // 2 else "B"
        else:
            team = "A" if i % 2 == 0 else "B" if len(chosen) > 1 else "unassigned"
        db.add(GameParticipant(user_id=p.id, game_id=game.id, team=team))
    return game


def create_dm_messages(db, users: list[User], n_conversations: int, msgs_per_conv: int) -> int:
    """Create DM conversations between users."""
    created = 0
    pairs = set()
    attempts = 0
    while len(pairs) < n_conversations and attempts < n_conversations * 3:
        attempts += 1
        if len(users) < 2:
            break
        u1, u2 = random.sample(users, 2)
        key = tuple(sorted([u1.id, u2.id]))
        if key in pairs:
            continue
        pairs.add(key)
        for i in range(msgs_per_conv):
            sender, recipient = (u1, u2) if i % 2 == 0 else (u2, u1)
            content = random.choice(DM_MESSAGES)
            t = _utcnow() - timedelta(days=random.randint(0, 21), hours=random.randint(0, 23))
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


def create_game_messages(db, games: list[Game]) -> int:
    """Add chat messages to games (participants only)."""
    created = 0
    games_with_participants = [
        g for g in games
        if db.query(GameParticipant).filter(GameParticipant.game_id == g.id).count() > 0
    ]
    for game in random.sample(games_with_participants, min(NUM_GAMES_WITH_CHAT, len(games_with_participants))):
        participants = (
            db.query(GameParticipant)
            .filter(GameParticipant.game_id == game.id)
            .all()
        )
        if not participants:
            continue
        n_msgs = random.randint(*MSG_PER_GAME_CHAT)
        for _ in range(n_msgs):
            p = random.choice(participants)
            content = random.choice(GAME_CHAT_MESSAGES)
            base_time = game.scheduled_time or _utcnow()
            t = base_time + timedelta(minutes=random.randint(-30, 90))
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


def create_pending_challenges(db, users: list[User], n: int) -> int:
    """Create pending, accepted, and in_progress challenges."""
    created = 0
    statuses = ["pending"] * 15 + ["accepted"] * 8 + ["in_progress"] * 7
    for i in range(n):
        if len(users) < 2:
            break
        u1, u2 = random.sample(users, 2)
        status = statuses[i % len(statuses)]
        c = Challenge(
            challenger_id=u1.id,
            challenged_id=u2.id,
            status=status,
            message="Let's run it at the CoRec!" if random.random() > 0.5 else None,
            scheduled_time=_utcnow() + timedelta(days=random.randint(1, 14)) if status != "pending" else None,
        )
        db.add(c)
        created += 1
    return created


def create_in_progress_game(db, users: list[User], game_type: str = "5v5") -> Game | None:
    """Create an in_progress game (full roster, no score yet)."""
    creator = random.choice(users)
    max_players = {"5v5": 10, "3v3": 6, "2v2": 4}[game_type]
    pool = [u for u in users if u.id != creator.id]
    if len(pool) < max_players - 1:
        return None
    chosen = [creator] + random.sample(pool, max_players - 1)
    cr_skill = creator.ai_skill_rating or 5.0
    skill_min = max(1.0, cr_skill - 2.0)
    skill_max = min(10.0, cr_skill + 2.0)
    game = Game(
        creator_id=creator.id,
        game_type=game_type,
        scheduled_time=_utcnow() - timedelta(minutes=15),
        skill_min=skill_min,
        skill_max=skill_max,
        status="in_progress",
        max_players=max_players,
    )
    db.add(game)
    db.flush()
    for i, p in enumerate(chosen):
        team = "A" if i < max_players // 2 else "B"
        db.add(GameParticipant(user_id=p.id, game_id=game.id, team=team))
    return game


def create_stats_contest(db, games: list[Game], users: list[User], n: int) -> int:
    """Create stats contests on completed games."""
    completed = [
        g for g in games
        if g.status == "completed" and g.stats_finalized
    ]
    created = 0
    for _ in range(n):
        if not completed:
            break
        game = random.choice(completed)
        participants = (
            db.query(GameParticipant)
            .filter(GameParticipant.game_id == game.id)
            .all()
        )
        if not participants:
            continue
        p = random.choice(participants)
        contester_id = p.user_id
        c = StatsContest(
            game_id=game.id,
            contester_id=contester_id,
            reason="I had 5 assists, not 3. Check the scorekeeper.",
            status="open",
        )
        db.add(c)
        created += 1
    return created


def create_reschedule_proposal(db, games: list[Game], users: list[User], n: int) -> int:
    """Create game reschedule proposals."""
    open_full = [g for g in games if g.status in ("open", "full") and g.scheduled_time]
    created = 0
    for _ in range(n):
        if not open_full:
            break
        game = random.choice(open_full)
        creator = db.query(User).filter(User.id == game.creator_id).first()
        if not creator:
            continue
        r = GameReschedule(
            game_id=game.id,
            proposed_scheduled_time=game.scheduled_time + timedelta(days=1),
            proposed_by_id=creator.id,
            status="pending",
        )
        db.add(r)
        created += 1
    return created


def fill_team_games_to_minimum(db, users: list[User], min_per_user: int) -> int:
    """Create games until every user has at least min_per_user team games (for high confidence)."""
    created = 0
    max_iter = 5000  # Safety cap
    game_types = ["2v2", "3v3", "5v5"]
    type_weights = [0.4, 0.4, 0.2]  # Prefer smaller games for faster fill

    for _ in range(max_iter):
        # Pick creator = user with fewest games (prioritize filling low users)
        users_sorted = sorted(users, key=lambda u: u.games_played)
        creator = users_sorted[0]
        if creator.games_played >= min_per_user:
            break

        gt = random.choices(game_types, weights=type_weights)[0]
        game = create_completed_game(db, users, gt, creator)
        if game:
            created += 1
            if created % 50 == 0:
                db.commit()
                users = db.query(User).filter(User.is_disabled == False).all()

    return created


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
        existing = db.query(User).filter(User.is_disabled == False).count()
        users = db.query(User).filter(User.is_disabled == False).all()

        if len(users) < NUM_USERS:
            n_create = NUM_USERS - len(users)
            print(f"  Creating {n_create} users (skill 1.0–10.0)...")
            new_users = create_users(db, n_create)
            print(f"  Created {len(new_users)} users")
            users = db.query(User).filter(User.is_disabled == False).all()

        print(f"  Total users: {len(users)}")
        if users:
            skills = [u.ai_skill_rating for u in users if u.ai_skill_rating]
            if skills:
                print(f"  Skill range: {min(skills):.1f} – {max(skills):.1f}")

        if len(users) < 10:
            print("  Need at least 10 users. Create more or run seed_e2e_user first.")
            return

        # Completed team games (base batch)
        completed = db.query(Game).filter(Game.status == "completed").count()
        target = NUM_COMPLETED_GAMES
        if completed < target:
            print(f"  Creating {target - completed} base completed team games...")
            for _ in range(target - completed):
                users_sorted = sorted(users, key=lambda u: u.games_played)
                creator = users_sorted[random.randint(0, min(19, len(users_sorted) - 1))]
                gt = random.choice(["5v5", "3v3", "2v2"])
                create_completed_game(db, users, gt, creator)
            db.commit()
            users = db.query(User).filter(User.is_disabled == False).all()
            completed = db.query(Game).filter(Game.status == "completed").count()
        print(f"  Base completed games: {completed}")

        # Fill team games until every user has MIN_TEAM_GAMES_PER_USER (high confidence)
        users = db.query(User).filter(User.is_disabled == False).all()
        min_games = min(u.games_played for u in users) if users else 0
        if min_games < MIN_TEAM_GAMES_PER_USER:
            need = sum(max(0, MIN_TEAM_GAMES_PER_USER - u.games_played) for u in users)
            print(f"  Filling team games until each user has {MIN_TEAM_GAMES_PER_USER}+ (est. {need} participations)...")
            extra = fill_team_games_to_minimum(db, users, MIN_TEAM_GAMES_PER_USER)
            db.commit()
            users = db.query(User).filter(User.is_disabled == False).all()
            print(f"  Added {extra} games. Completed: {db.query(Game).filter(Game.status == 'completed').count()}")
        completed = db.query(Game).filter(Game.status == "completed").count()
        print(f"  Total completed games: {completed}")

        # 1v1 challenges (distribute so each user gets ~MIN_CHALLENGES_PER_USER)
        users = db.query(User).filter(User.is_disabled == False).all()
        total_ch = sum(u.challenge_wins + u.challenge_losses for u in users)
        target_ch = NUM_USERS * MIN_CHALLENGES_PER_USER
        if total_ch < target_ch:
            to_create = target_ch - total_ch
            print(f"  Creating {to_create} completed 1v1 challenges (~{MIN_CHALLENGES_PER_USER} per user)...")
            for _ in range(to_create):
                users_sorted = sorted(users, key=lambda u: u.challenge_wins + u.challenge_losses)
                u1 = users_sorted[random.randint(0, min(29, len(users_sorted) - 1))]
                others = [u for u in users if u.id != u1.id]
                u2 = random.choice(others) if others else u1
                create_challenge(db, u1, u2)
            db.commit()
        print(f"  Completed 1v1 challenges: {db.query(Challenge).filter(Challenge.status == 'completed').count()}")

        # Pending/accepted challenges
        pending_ch = db.query(Challenge).filter(
            Challenge.status.in_(["pending", "accepted", "in_progress"])
        ).count()
        if pending_ch < NUM_PENDING_CHALLENGES:
            print(f"  Creating {NUM_PENDING_CHALLENGES - pending_ch} pending/accepted challenges...")
            create_pending_challenges(db, users, NUM_PENDING_CHALLENGES - pending_ch)
            db.commit()
        print(f"  Pending/accepted challenges: {db.query(Challenge).filter(Challenge.status.in_(['pending', 'accepted', 'in_progress'])).count()}")

        # Open/full games
        open_count = db.query(Game).filter(Game.status.in_(["open", "full"])).count()
        if open_count < NUM_OPEN_FULL_GAMES:
            print(f"  Creating {NUM_OPEN_FULL_GAMES - open_count} open/full games...")
            for _ in range(NUM_OPEN_FULL_GAMES - open_count):
                creator = random.choice(users)
                gt = random.choice(["5v5", "3v3", "2v2"])
                create_open_game(db, users, gt, creator)
            db.commit()
        print(f"  Open/full games: {db.query(Game).filter(Game.status.in_(['open', 'full'])).count()}")

        # In-progress games
        in_progress = db.query(Game).filter(Game.status == "in_progress").count()
        if in_progress < NUM_IN_PROGRESS_GAMES:
            print(f"  Creating {NUM_IN_PROGRESS_GAMES - in_progress} in-progress games...")
            for _ in range(NUM_IN_PROGRESS_GAMES - in_progress):
                gt = random.choice(["5v5", "3v3", "2v2"])
                create_in_progress_game(db, users, gt)
            db.commit()
        print(f"  In-progress games: {db.query(Game).filter(Game.status == 'in_progress').count()}")

        # DM messages
        dm_count = db.query(Message).filter(Message.game_id.is_(None)).count()
        target_dm = NUM_DM_CONVERSATIONS * MSG_PER_DM_CONV
        if dm_count < target_dm:
            print(f"  Creating DM conversations ({NUM_DM_CONVERSATIONS} convos, ~{MSG_PER_DM_CONV} msgs each)...")
            create_dm_messages(db, users, NUM_DM_CONVERSATIONS, MSG_PER_DM_CONV)
            db.commit()
            dm_count = db.query(Message).filter(Message.game_id.is_(None)).count()
        print(f"  DM messages: {dm_count}")

        # Game chat messages
        all_games = db.query(Game).all()
        game_msg_count = db.query(Message).filter(Message.game_id.isnot(None)).count()
        target_game_msg = NUM_GAMES_WITH_CHAT * (MSG_PER_GAME_CHAT[0] + MSG_PER_GAME_CHAT[1]) // 2
        if game_msg_count < target_game_msg:
            print(f"  Creating game chat messages...")
            create_game_messages(db, all_games)
            db.commit()
            game_msg_count = db.query(Message).filter(Message.game_id.isnot(None)).count()
        print(f"  Game chat messages: {game_msg_count}")

        # Stats contests
        contest_count = db.query(StatsContest).count()
        if contest_count < NUM_STATS_CONTESTS:
            print(f"  Creating {NUM_STATS_CONTESTS - contest_count} stats contests...")
            create_stats_contest(db, all_games, users, NUM_STATS_CONTESTS - contest_count)
            db.commit()

        # Reschedule proposals
        reschedule_count = db.query(GameReschedule).count()
        if reschedule_count < NUM_RESCHEDULE_PROPOSALS:
            print(f"  Creating {NUM_RESCHEDULE_PROPOSALS - reschedule_count} reschedule proposals...")
            create_reschedule_proposal(db, all_games, users, NUM_RESCHEDULE_PROPOSALS - reschedule_count)
            db.commit()

        # Backfill skill ratings from completed games
        print("  Backfilling skill ratings (leaderboard)...")
        backfill_skill_ratings(db)
        db.commit()

        # Final stats
        users = db.query(User).filter(User.is_disabled == False).all()
        skills = [u.ai_skill_rating for u in users if u.ai_skill_rating]
        total_games = [(u.games_played + u.challenge_wins + u.challenge_losses) for u in users]
        confidences = [round(100 * (1 - __import__("math").exp(-tg / 6)), 0) for tg in total_games]
        print(f"\n  Skill range: {min(skills):.1f} – {max(skills):.1f}" if skills else "")
        print(f"  Team games/user: min={min(u.games_played for u in users)}, max={max(u.games_played for u in users)}, avg={sum(u.games_played for u in users)/len(users):.0f}")
        print(f"  Confidence: min={min(confidences):.0f}%, max={max(confidences):.0f}%, avg={sum(confidences)/len(confidences):.0f}%")

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
