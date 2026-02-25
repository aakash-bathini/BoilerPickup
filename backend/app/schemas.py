from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, field_serializer

from app.time_utils import to_est_isoformat


# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────

class UserRegister(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    height: Optional[str] = None
    weight: Optional[int] = Field(None, ge=50, le=500)
    preferred_position: Optional[str] = None
    self_reported_skill: int = Field(..., ge=1, le=10)

    @field_validator("email")
    @classmethod
    def validate_allowed_email(cls, v: str) -> str:
        low = v.lower()
        if not (low.endswith("@purdue.edu") or low.endswith("@purdoo.com")):
            raise ValueError("Must use a @purdue.edu or @purdoo.com email address")
        return low

    @field_validator("preferred_position")
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in ("PG", "SG", "SF", "PF", "C"):
            raise ValueError("Position must be PG, SG, SF, PF, or C")
        return v.upper() if v else None


class UserLogin(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str = Field(..., max_length=255)
    code: str = Field(..., min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validate_purdue_email(cls, v: str) -> str:
        if not v.lower().endswith("@purdue.edu"):
            raise ValueError("Must use a @purdue.edu email address to verify")
        return v.lower()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ──────────────────────────────────────────────
# User responses
# ──────────────────────────────────────────────

class UserPublic(BaseModel):
    id: int
    username: str
    display_name: str
    height: Optional[str] = None
    weight: Optional[int] = None
    preferred_position: Optional[str] = None
    self_reported_skill: int
    ai_skill_rating: float
    skill_confidence: float
    games_played: int
    wins: int
    losses: int
    challenge_wins: int = 0
    challenge_losses: int = 0
    bio: Optional[str] = None
    is_disabled: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    height: Optional[str] = None
    weight: Optional[int] = Field(None, ge=50, le=500)
    preferred_position: Optional[str] = None
    bio: Optional[str] = None

    @field_validator("preferred_position")
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.upper() not in ("PG", "SG", "SF", "PF", "C"):
            raise ValueError("Position must be PG, SG, SF, PF, or C")
        return v.upper() if v else None


class UserSearchResult(BaseModel):
    id: int
    username: str
    display_name: str
    ai_skill_rating: float
    preferred_position: Optional[str] = None
    games_played: int
    wins: int = 0
    losses: int = 0
    challenge_wins: int = 0
    challenge_losses: int = 0
    skill_rating_change_week: Optional[float] = None  # gain over past 7 days (Players on Fire)

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Game
# ──────────────────────────────────────────────

class GameCreate(BaseModel):
    game_type: str = Field(..., pattern=r"^(5v5|3v3|2v2)$")
    scheduled_time: datetime
    skill_min: float = Field(1.0, ge=1.0, le=10.0)
    skill_max: float = Field(10.0, ge=1.0, le=10.0)
    court_type: str = Field("fullcourt", pattern=r"^(fullcourt|halfcourt)$")
    notes: Optional[str] = None

    @field_validator("skill_max")
    @classmethod
    def max_gte_min(cls, v: float, info) -> float:
        if "skill_min" in info.data and v < info.data["skill_min"]:
            raise ValueError("skill_max must be >= skill_min")
        return v


class GameUpdate(BaseModel):
    """For editing game when no one else has joined."""
    scheduled_time: Optional[datetime] = None
    skill_min: Optional[float] = Field(None, ge=1.0, le=10.0)
    skill_max: Optional[float] = Field(None, ge=1.0, le=10.0)
    court_type: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("court_type")
    @classmethod
    def court_type_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("fullcourt", "halfcourt"):
            raise ValueError("court_type must be fullcourt or halfcourt")
        return v


class GameParticipantOut(BaseModel):
    id: int
    user_id: int
    team: str
    username: Optional[str] = None
    display_name: Optional[str] = None
    ai_skill_rating: Optional[float] = None
    preferred_position: Optional[str] = None

    model_config = {"from_attributes": True}


class GameOut(BaseModel):
    id: int
    creator_id: int
    game_type: str
    scheduled_time: datetime
    skill_min: float
    skill_max: float
    status: str
    court_type: str
    team_a_score: Optional[int] = None
    team_b_score: Optional[int] = None
    max_players: int
    notes: Optional[str] = None
    created_at: datetime
    participants: list[GameParticipantOut] = []
    creator_name: Optional[str] = None
    scorekeeper_id: Optional[int] = None
    scorekeeper_status: Optional[str] = None
    scorekeeper_name: Optional[str] = None
    stats_finalized: bool = False
    stats_finalized_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    win_prediction: Optional[float] = None  # P(Team A wins), 0-1, when roster full

    model_config = {"from_attributes": True}

    @field_serializer("scheduled_time", "created_at", "stats_finalized_at", "completed_at")
    def _ser_datetime(self, v: datetime | None) -> str | None:
        return to_est_isoformat(v) if v is not None else None


class GameComplete(BaseModel):
    team_a_score: int = Field(..., ge=0, le=100)
    team_b_score: int = Field(..., ge=0, le=100)


class GameReschedulePropose(BaseModel):
    scheduled_time: datetime


class GameRescheduleVoteIn(BaseModel):
    approved: bool


class GameRescheduleOut(BaseModel):
    id: int
    game_id: int
    proposed_scheduled_time: datetime
    proposed_by_id: int
    status: str
    votes_for: int = 0
    votes_against: int = 0
    total_participants: int = 0
    created_at: datetime

    @field_serializer("proposed_scheduled_time", "created_at")
    def _ser_datetime(self, v: datetime | None) -> str | None:
        return to_est_isoformat(v) if v is not None else None


# ──────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────

class PlayerStatsSubmit(BaseModel):
    user_id: int
    pts: int = Field(0, ge=0)
    reb: int = Field(0, ge=0)
    ast: int = Field(0, ge=0)
    stl: int = Field(0, ge=0)
    blk: int = Field(0, ge=0)
    tov: int = Field(0, ge=0)
    fgm: int = Field(0, ge=0)
    fga: int = Field(0, ge=0)
    three_pm: int = Field(0, ge=0)
    three_pa: int = Field(0, ge=0)
    ftm: int = Field(0, ge=0)
    fta: int = Field(0, ge=0)

    @field_validator("fga")
    @classmethod
    def fga_gte_fgm(cls, v: int, info) -> int:
        if "fgm" in info.data and v < info.data["fgm"]:
            raise ValueError("fga must be >= fgm")
        return v

    @field_validator("three_pa")
    @classmethod
    def three_pa_gte_three_pm(cls, v: int, info) -> int:
        if "three_pm" in info.data and v < info.data["three_pm"]:
            raise ValueError("three_pa must be >= three_pm")
        return v

    @field_validator("fta")
    @classmethod
    def fta_gte_ftm(cls, v: int, info) -> int:
        if "ftm" in info.data and v < info.data["ftm"]:
            raise ValueError("fta must be >= ftm")
        return v


class BulkStatsSubmit(BaseModel):
    stats: list[PlayerStatsSubmit]


class PlayerStatsOut(BaseModel):
    id: int
    user_id: int
    game_id: int
    pts: int
    reb: int
    ast: int
    stl: int
    blk: int
    tov: int
    fgm: int
    fga: int
    three_pm: int
    three_pa: int
    ftm: int
    fta: int

    model_config = {"from_attributes": True}


class CareerStats(BaseModel):
    games_played: int
    wins: int
    losses: int
    win_rate: float
    challenge_wins: int = 0
    challenge_losses: int = 0
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    topg: float
    fg_pct: float
    three_pct: float
    ft_pct: float
    total_pts: int
    total_reb: int
    total_ast: int
    total_stl: int
    total_blk: int
    total_tov: int


class CareerStatsByGameType(BaseModel):
    """Stats for a single game type (5v5, 3v3, 2v2)."""
    games_played: int
    ppg: float
    rpg: float
    apg: float
    spg: float
    bpg: float
    topg: float
    fg_pct: float
    three_pct: float
    ft_pct: float


class CareerStatsByTypeOut(BaseModel):
    """Career averages split by game type."""
    five_v_five: CareerStatsByGameType
    three_v_three: CareerStatsByGameType
    two_v_two: CareerStatsByGameType


class SkillHistoryEntry(BaseModel):
    """Single point in skill rating progression."""
    timestamp: datetime
    rating: float

    @field_serializer("timestamp")
    def _ser_ts(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


class GameStatsHistoryEntry(BaseModel):
    game_id: int
    game_type: str
    scheduled_time: datetime
    pts: int
    reb: int
    ast: int
    stl: int
    blk: int
    tov: int
    fgm: int
    fga: int
    three_pm: int
    three_pa: int
    ftm: int
    fta: int
    skill_before: Optional[float] = None
    skill_after: Optional[float] = None

    @field_serializer("scheduled_time")
    def _ser_scheduled_time(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


# ──────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────

class MessageCreate(BaseModel):
    game_id: Optional[int] = None
    recipient_id: Optional[int] = None
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message content cannot be blank")
        return v.strip()


class MessageOut(BaseModel):
    id: int
    sender_id: int
    game_id: Optional[int] = None
    recipient_id: Optional[int] = None
    content: str
    created_at: datetime
    sender_name: Optional[str] = None
    sender_username: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


class ConversationPreview(BaseModel):
    user_id: int
    username: str
    display_name: str
    last_message: str
    last_message_time: datetime

    @field_serializer("last_message_time")
    def _ser_last_message_time(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


# ──────────────────────────────────────────────
# Challenges (1v1)
# ──────────────────────────────────────────────

class ChallengeCreate(BaseModel):
    challenged_id: int
    scheduled_time: datetime = Field(
        ...,
        description="When the 1v1 will be played. Required so both players know when to meet.",
    )
    message: Optional[str] = Field(None, max_length=500)


class ChallengeScoreSubmit(BaseModel):
    my_score: int = Field(..., ge=0, le=15)
    opponent_score: int = Field(..., ge=0, le=15)


class ChallengeOut(BaseModel):
    id: int
    challenger_id: int
    challenged_id: int
    status: str
    scheduled_time: Optional[datetime] = None
    message: Optional[str] = None
    challenger_score: Optional[int] = None
    challenged_score: Optional[int] = None
    challenger_confirmed: bool
    challenged_confirmed: bool
    winner_id: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    challenger_name: Optional[str] = None
    challenged_name: Optional[str] = None
    challenger_win_probability: Optional[float] = None  # P(challenger wins), 0-1

    model_config = {"from_attributes": True}

    @field_serializer("scheduled_time", "created_at", "completed_at")
    def _ser_datetime(self, v: datetime | None) -> str | None:
        return to_est_isoformat(v) if v is not None else None


# ──────────────────────────────────────────────
# Moderation (Report / Block)
# ──────────────────────────────────────────────

class ReportCreate(BaseModel):
    reported_id: int
    reason: str = Field(..., min_length=1, max_length=50)
    details: Optional[str] = Field(None, max_length=1000)


class ReportOut(BaseModel):
    id: int
    reporter_id: int
    reported_id: int
    reason: str
    details: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


class BlockOut(BaseModel):
    id: int
    blocker_id: int
    blocked_id: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_created_at(self, v: datetime) -> str:
        return to_est_isoformat(v) or ""


# ──────────────────────────────────────────────
# Stats Contest
# ──────────────────────────────────────────────

class ContestCreate(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class ContestVoteIn(BaseModel):
    support: bool


class ContestOut(BaseModel):
    id: int
    game_id: int
    contester_id: int
    reason: str
    status: str
    votes_for: int
    votes_against: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    contester_name: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_serializer("created_at", "resolved_at")
    def _ser_datetime(self, v: datetime | None) -> str | None:
        return to_est_isoformat(v) if v is not None else None


# ──────────────────────────────────────────────
# Scorekeeper
# ──────────────────────────────────────────────

class ScorekeeperInvite(BaseModel):
    user_id: int
