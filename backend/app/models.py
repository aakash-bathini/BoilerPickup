from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, CheckConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    height = Column(String(10), nullable=True)
    weight = Column(Integer, nullable=True)
    preferred_position = Column(String(2), nullable=True)
    gender = Column(String(10), nullable=True)  # male, female, other — for NBA height mapping
    self_reported_skill = Column(Integer, nullable=False, default=5)
    ai_skill_rating = Column(Float, nullable=False, default=5.0)
    skill_confidence = Column(Float, nullable=False, default=0.1)
    games_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    challenge_wins = Column(Integer, nullable=False, default=0)
    challenge_losses = Column(Integer, nullable=False, default=0)
    bio = Column(Text, nullable=True, default="")
    is_disabled = Column(Boolean, nullable=False, default=False)
    unconfirmed_challenges = Column(Integer, nullable=False, default=0)
    report_count = Column(Integer, nullable=False, default=0)
    email_verified = Column(Boolean, nullable=False, default=False)
    verification_code = Column(String(6), nullable=True)
    verification_code_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    game_participations = relationship("GameParticipant", back_populates="user")
    player_stats = relationship("PlayerGameStats", back_populates="user")
    skill_history = relationship("SkillHistory", back_populates="user")
    created_games = relationship("Game", back_populates="creator", foreign_keys="Game.creator_id")
    sent_messages = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")

    __table_args__ = (
        CheckConstraint("self_reported_skill >= 1 AND self_reported_skill <= 10", name="check_self_skill_range"),
    )


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_type = Column(String(3), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    skill_min = Column(Float, nullable=False, default=1.0)
    skill_max = Column(Float, nullable=False, default=10.0)
    status = Column(String(20), nullable=False, default="open")
    court_type = Column(String(15), nullable=False, default="fullcourt")
    team_a_score = Column(Integer, nullable=True)
    team_b_score = Column(Integer, nullable=True)
    max_players = Column(Integer, nullable=False, default=10)
    notes = Column(Text, nullable=True, default="")
    scorekeeper_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    scorekeeper_status = Column(String(20), nullable=True)
    stats_finalized = Column(Boolean, nullable=False, default=False)
    stats_finalized_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    creator = relationship("User", back_populates="created_games", foreign_keys=[creator_id])
    scorekeeper = relationship("User", foreign_keys=[scorekeeper_id])
    participants = relationship("GameParticipant", back_populates="game", cascade="all, delete-orphan")
    player_stats = relationship("PlayerGameStats", back_populates="game", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="game", cascade="all, delete-orphan")
    contests = relationship("StatsContest", back_populates="game", cascade="all, delete-orphan")
    reschedule_proposals = relationship("GameReschedule", back_populates="game", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("game_type IN ('5v5', '3v3', '2v2')", name="check_game_type"),
        CheckConstraint("status IN ('open', 'full', 'in_progress', 'completed')", name="check_game_status"),
        CheckConstraint("court_type IN ('fullcourt', 'halfcourt')", name="check_court_type"),
    )


class GameParticipant(Base):
    __tablename__ = "game_participants"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    team = Column(String(12), nullable=False, default="unassigned")

    user = relationship("User", back_populates="game_participations")
    game = relationship("Game", back_populates="participants")

    __table_args__ = (
        CheckConstraint("team IN ('A', 'B', 'unassigned')", name="check_team_value"),
    )


class PlayerGameStats(Base):
    __tablename__ = "player_game_stats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    pts = Column(Integer, nullable=False, default=0)
    reb = Column(Integer, nullable=False, default=0)
    ast = Column(Integer, nullable=False, default=0)
    stl = Column(Integer, nullable=False, default=0)
    blk = Column(Integer, nullable=False, default=0)
    tov = Column(Integer, nullable=False, default=0)
    fgm = Column(Integer, nullable=False, default=0)
    fga = Column(Integer, nullable=False, default=0)
    three_pm = Column(Integer, nullable=False, default=0)
    three_pa = Column(Integer, nullable=False, default=0)
    ftm = Column(Integer, nullable=False, default=0)
    fta = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="player_stats")
    game = relationship("Game", back_populates="player_stats")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True)
    recipient_id = Column(Integer, nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    sender = relationship("User", back_populates="sent_messages", foreign_keys=[sender_id])
    game = relationship("Game", back_populates="messages")


class SkillHistory(Base):
    __tablename__ = "skill_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, nullable=True)
    challenge_id = Column(Integer, nullable=True)
    old_rating = Column(Float, nullable=False)
    new_rating = Column(Float, nullable=False)
    game_type = Column(String(3), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=_utcnow)

    user = relationship("User", back_populates="skill_history")


class Challenge(Base):
    """1v1 challenges issued via DM. Tracked separately from team games."""
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    challenger_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    challenged_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    scheduled_time = Column(DateTime, nullable=True)
    message = Column(Text, nullable=True)
    challenger_score = Column(Integer, nullable=True)
    challenged_score = Column(Integer, nullable=True)
    challenger_confirmed = Column(Boolean, nullable=False, default=False)
    challenged_confirmed = Column(Boolean, nullable=False, default=False)
    winner_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    challenger = relationship("User", foreign_keys=[challenger_id])
    challenged = relationship("User", foreign_keys=[challenged_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'in_progress', 'awaiting_confirmation', 'completed', 'declined', 'expired')",
            name="check_challenge_status",
        ),
    )


class PendingRegistration(Base):
    """Stores registration data until email is verified. Account created only after verification."""
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    height = Column(String(10), nullable=True)
    weight = Column(Integer, nullable=True)
    preferred_position = Column(String(2), nullable=True)
    gender = Column(String(10), nullable=True)
    self_reported_skill = Column(Integer, nullable=False, default=5)
    verification_code = Column(String(6), nullable=False)
    verification_code_expires = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class Block(Base):
    __tablename__ = "blocks"

    id = Column(Integer, primary_key=True, index=True)
    blocker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    blocked_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    blocker = relationship("User", foreign_keys=[blocker_id])
    blocked = relationship("User", foreign_keys=[blocked_id])


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reported_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    reporter = relationship("User", foreign_keys=[reporter_id])
    reported = relationship("User", foreign_keys=[reported_id])


class GameReschedule(Base):
    """Creator proposes new time; participants vote. Approved when all vote yes."""
    __tablename__ = "game_reschedules"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    proposed_scheduled_time = Column(DateTime, nullable=False)
    proposed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    game = relationship("Game", back_populates="reschedule_proposals")
    proposed_by = relationship("User", foreign_keys=[proposed_by_id])
    votes = relationship("GameRescheduleVote", back_populates="reschedule", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="check_reschedule_status"),
    )


class GameRescheduleVote(Base):
    __tablename__ = "game_reschedule_votes"

    id = Column(Integer, primary_key=True, index=True)
    reschedule_id = Column(Integer, ForeignKey("game_reschedules.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approved = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    reschedule = relationship("GameReschedule", back_populates="votes")
    user = relationship("User", foreign_keys=[user_id])


class StatsContest(Base):
    """A challenge to game stats within the 24h review period."""
    __tablename__ = "stats_contests"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    contester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    votes_for = Column(Integer, nullable=False, default=0)
    votes_against = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    resolved_at = Column(DateTime, nullable=True)

    game = relationship("Game", back_populates="contests")
    contester = relationship("User", foreign_keys=[contester_id])
    votes = relationship("ContestVote", back_populates="contest", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('open', 'approved', 'rejected')", name="check_contest_status"),
    )


class ContestVote(Base):
    __tablename__ = "contest_votes"

    id = Column(Integer, primary_key=True, index=True)
    contest_id = Column(Integer, ForeignKey("stats_contests.id"), nullable=False)
    voter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vote = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    contest = relationship("StatsContest", back_populates="votes")
    voter = relationship("User", foreign_keys=[voter_id])
