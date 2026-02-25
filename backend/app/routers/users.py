from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.time_utils import to_est_isoformat
from app.models import User, Block, PlayerGameStats, PendingRegistration, SkillHistory
from app.ai.player_match import find_matches
from pydantic import BaseModel, Field

from app.schemas import (
    UserRegister, UserLogin, Token, UserPublic, UserUpdate, UserSearchResult,
    VerifyEmailRequest,
)
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.email_service import generate_code, send_verification_email

router = APIRouter(prefix="/api", tags=["users"])


def _get_blocked_ids(db: Session, user_id: int) -> set[int]:
    blocks = db.query(Block).filter(
        or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
    ).all()
    ids = set()
    for b in blocks:
        ids.add(b.blocker_id if b.blocked_id == user_id else b.blocked_id)
    return ids


def _is_purdoo_test_email(email: str) -> bool:
    """purdoo.com emails skip verification for testing."""
    return email.lower().endswith("@purdoo.com")


@router.post("/auth/register", status_code=status.HTTP_200_OK)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """Send verification code for @purdue.edu. @purdoo.com creates account immediately (testing)."""
    email_low = data.email.lower()
    if db.query(User).filter(User.email == email_low).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(PendingRegistration).filter(PendingRegistration.username == data.username).first():
        raise HTTPException(status_code=409, detail="Username already taken")
    if db.query(PendingRegistration).filter(PendingRegistration.email == email_low).first():
        raise HTTPException(status_code=409, detail="Verification already sent. Check your email or request a new code.")

    if _is_purdoo_test_email(email_low):
        user = User(
            email=email_low,
            username=data.username,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
            height=data.height,
            weight=data.weight,
            preferred_position=data.preferred_position,
            self_reported_skill=data.self_reported_skill,
            ai_skill_rating=float(data.self_reported_skill),
            email_verified=True,
        )
        db.add(user)
        db.commit()
        return {"message": "Account created (purdoo.com test account — no verification required)"}

    code = generate_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)

    pending = PendingRegistration(
        email=email_low,
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
        height=data.height,
        weight=data.weight,
        preferred_position=data.preferred_position,
        self_reported_skill=data.self_reported_skill,
        verification_code=code,
        verification_code_expires=expires,
    )
    db.add(pending)
    db.commit()

    ok, err = send_verification_email(data.email, code)
    if not ok:
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=503,
            detail=err or "Could not send verification email. Configure SMTP in backend/.env (SMTP_HOST, SMTP_USER, SMTP_PASSWORD).",
        )
    return {"message": "Verification code sent to your email"}


@router.post("/auth/verify-email")
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify code and create account from PendingRegistration. Or verify existing user."""
    email = data.email.lower()

    # New flow: pending registration
    pending = db.query(PendingRegistration).filter(PendingRegistration.email == email).first()
    if pending:
        if pending.verification_code != data.code:
            raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        now = datetime.now(timezone.utc)
        expires = pending.verification_code_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            raise HTTPException(status_code=400, detail="Verification code expired. Request a new one.")
        if db.query(User).filter(User.username == pending.username).first():
            db.delete(pending)
            db.commit()
            raise HTTPException(status_code=409, detail="Username was taken. Please register again.")

        user = User(
            email=pending.email,
            username=pending.username,
            password_hash=pending.password_hash,
            display_name=pending.display_name,
            height=pending.height,
            weight=pending.weight,
            preferred_position=pending.preferred_position,
            self_reported_skill=pending.self_reported_skill,
            ai_skill_rating=float(pending.self_reported_skill),
            email_verified=True,
        )
        db.add(user)
        db.delete(pending)
        db.commit()
        db.refresh(user)
        return {"message": "Account created successfully"}

    # Legacy: existing user (pre-verify flow)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found. Complete sign up first.")
    if user.email_verified:
        return {"message": "Email already verified"}
    if not user.verification_code or user.verification_code != data.code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    if user.verification_code_expires and user.verification_code_expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired. Request a new one.")
    user.email_verified = True
    user.verification_code = None
    user.verification_code_expires = None
    db.commit()
    return {"message": "Email verified successfully"}


class ResendCodeRequest(BaseModel):
    email: str = Field(..., max_length=255)


@router.post("/auth/resend-code")
def resend_verification_code(data: ResendCodeRequest, db: Session = Depends(get_db)):
    if not data.email.lower().endswith("@purdue.edu"):
        raise HTTPException(status_code=400, detail="Must use a @purdue.edu email")
    email = data.email.lower()

    pending = db.query(PendingRegistration).filter(PendingRegistration.email == email).first()
    if pending:
        code = generate_code()
        expires = datetime.now(timezone.utc) + timedelta(minutes=15)
        pending.verification_code = code
        pending.verification_code_expires = expires
        db.commit()
        ok, err = send_verification_email(email, code)
        if not ok:
            raise HTTPException(status_code=503, detail=err or "Could not send email. Configure SMTP in backend/.env.")
        return {"message": "Verification code sent"}

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found. Complete sign up first.")
    if user.email_verified:
        return {"message": "Email already verified"}
    code = generate_code()
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    user.verification_code = code
    user.verification_code_expires = expires
    db.commit()
    ok, err = send_verification_email(email, code)
    if not ok:
        raise HTTPException(status_code=503, detail=err or "Could not send email")
    return {"message": "Verification code sent"}


@router.post("/auth/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email.lower()).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.email_verified is False:
        raise HTTPException(status_code=403, detail="Please verify your email first. Check your inbox for the verification code.")
    if user.is_disabled:
        raise HTTPException(status_code=403, detail="Your account has been disabled due to multiple reports")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get("/users/me", response_model=UserPublic)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/users/me", response_model=UserPublic)
def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


def _user_ids_with_min_stats(db: Session, min_ppg=None, min_rpg=None, min_apg=None, min_spg=None, min_bpg=None, min_fg_pct=None):
    """Return user IDs whose career averages meet the given minimums."""
    from sqlalchemy import func, and_
    filters = []
    if min_ppg is not None:
        filters.append(func.avg(PlayerGameStats.pts) >= min_ppg)
    if min_rpg is not None:
        filters.append(func.avg(PlayerGameStats.reb) >= min_rpg)
    if min_apg is not None:
        filters.append(func.avg(PlayerGameStats.ast) >= min_apg)
    if min_spg is not None:
        filters.append(func.avg(PlayerGameStats.stl) >= min_spg)
    if min_bpg is not None:
        filters.append(func.avg(PlayerGameStats.blk) >= min_bpg)
    if min_fg_pct is not None:
        filters.append(100.0 * func.sum(PlayerGameStats.fgm) / func.nullif(func.sum(PlayerGameStats.fga), 0) >= min_fg_pct)
    if not filters:
        return None
    q = db.query(PlayerGameStats.user_id).group_by(PlayerGameStats.user_id).having(and_(*filters))
    return [r[0] for r in q.all()]


@router.get("/users/search", response_model=list[UserSearchResult])
def search_users(
    q: str = Query(None, min_length=0),
    position: Optional[str] = Query(None, pattern=r"^(PG|SG|SF|PF|C)$"),
    min_skill: Optional[float] = Query(None, ge=1.0, le=10.0),
    max_skill: Optional[float] = Query(None, ge=1.0, le=10.0),
    min_games: Optional[int] = Query(None, ge=0),
    min_wins: Optional[int] = Query(None, ge=0),
    min_ppg: Optional[float] = Query(None, ge=0),
    min_rpg: Optional[float] = Query(None, ge=0),
    min_apg: Optional[float] = Query(None, ge=0),
    min_spg: Optional[float] = Query(None, ge=0),
    min_bpg: Optional[float] = Query(None, ge=0),
    min_fg_pct: Optional[float] = Query(None, ge=0, le=100),
    sort_by: Optional[str] = Query(None, pattern=r"^(skill|games|wins|name)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blocked_ids = _get_blocked_ids(db, current_user.id)
    query = db.query(User).filter(User.is_disabled == False, User.id != current_user.id)

    if q and q.strip():
        query = query.filter(
            User.display_name.ilike(f"%{q}%") | User.username.ilike(f"%{q}%")
        )
    if position:
        query = query.filter(User.preferred_position == position)
    if min_skill is not None:
        query = query.filter(User.ai_skill_rating >= min_skill)
    if max_skill is not None:
        query = query.filter(User.ai_skill_rating <= max_skill)
    if min_games is not None:
        query = query.filter(User.games_played >= min_games)
    if min_wins is not None:
        query = query.filter(User.wins >= min_wins)
    if blocked_ids:
        query = query.filter(~User.id.in_(blocked_ids))

    stat_ids = _user_ids_with_min_stats(db, min_ppg, min_rpg, min_apg, min_spg, min_bpg, min_fg_pct)
    if stat_ids is not None:
        query = query.filter(User.id.in_(stat_ids))

    if sort_by == "skill":
        query = query.order_by(User.ai_skill_rating.desc())
    elif sort_by == "games":
        query = query.order_by(User.games_played.desc())
    elif sort_by == "wins":
        query = query.order_by(User.wins.desc())
    elif sort_by == "name":
        query = query.order_by(User.display_name.asc())
    else:
        query = query.order_by(User.ai_skill_rating.desc())

    results = query.limit(30).all()
    return results


@router.get("/users/match", response_model=list[UserSearchResult])
def get_match(
    limit: int = Query(10, ge=1, le=20),
    skill_tolerance: float = Query(1.5, ge=0, le=5),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """ML-based: find players similar in skill, height, position. For matchmaking."""
    if current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Account disabled")
    users = find_matches(db, current_user.id, limit=limit, skill_tolerance=skill_tolerance)
    return users


@router.get("/users/leaderboard-1v1", response_model=list[UserSearchResult])
def leaderboard_1v1(
    limit: int = Query(50, ge=1, le=100),
    sort: Optional[str] = Query(None, pattern=r"^(wins_total|wins_week)$"),
    db: Session = Depends(get_db),
):
    """1v1-only rankings: most head-to-head wins (total or last 7 days)."""
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    if sort == "wins_week":
        # 1v1 wins in last 7 days — need to join Challenge
        from app.models import Challenge
        wins_week_subq = (
            db.query(Challenge.winner_id, func.count(Challenge.id).label("wins"))
            .filter(Challenge.status == "completed", Challenge.completed_at >= week_ago, Challenge.winner_id.isnot(None))
            .group_by(Challenge.winner_id)
            .subquery()
        )
        query = (
            db.query(User)
            .outerjoin(wins_week_subq, User.id == wins_week_subq.c.winner_id)
            .filter(User.is_disabled == False)
            .filter(User.challenge_wins + User.challenge_losses >= 1)
        )
        # Order by wins this week desc, then total challenge_wins desc
        wins_col = func.coalesce(wins_week_subq.c.wins, 0)
        query = query.order_by(wins_col.desc(), User.challenge_wins.desc()).limit(limit)
        results = query.all()
    else:
        # Default: sort by total 1v1 wins
        query = (
            db.query(User)
            .filter(User.is_disabled == False)
            .filter(User.challenge_wins + User.challenge_losses >= 1)
            .order_by(User.challenge_wins.desc(), User.ai_skill_rating.desc())
            .limit(limit)
        )
        results = query.all()

    out = []
    for u in results:
        out.append(UserSearchResult(
            id=u.id, username=u.username, display_name=u.display_name,
            ai_skill_rating=u.ai_skill_rating, preferred_position=u.preferred_position,
            games_played=u.games_played or 0, wins=u.wins or 0, losses=u.losses or 0,
            challenge_wins=u.challenge_wins or 0, challenge_losses=u.challenge_losses or 0,
        ))
    return out


@router.get("/users/leaderboard", response_model=list[UserSearchResult])
def leaderboard(
    limit: int = Query(50, ge=1, le=100),
    position: Optional[str] = Query(None, pattern=r"^(PG|SG|SF|PF|C)$"),
    sort: Optional[str] = Query(None, pattern=r"^(overall|position|hot_week)$"),
    db: Session = Depends(get_db),
):
    """Leaderboard: best overall, by position, or hottest (fastest rising skill over past week)."""
    from sqlalchemy import func
    from datetime import datetime, timezone, timedelta

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    if sort == "hot_week":
        # Players on Fire: skill gain over past 7 days from SkillHistory
        gain_subq = (
            db.query(
                SkillHistory.user_id,
                func.sum(SkillHistory.new_rating - SkillHistory.old_rating).label("gain"),
            )
            .filter(SkillHistory.timestamp >= week_ago)
            .group_by(SkillHistory.user_id)
            .subquery()
        )
        total_games_expr = User.games_played + User.challenge_wins + User.challenge_losses
        # Include both positive and negative gain when few players (e.g. 2 after first 1v1)
        query = (
            db.query(User, gain_subq.c.gain)
            .join(gain_subq, User.id == gain_subq.c.user_id)
            .filter(User.is_disabled == False)
            .filter(total_games_expr >= 1)
        )
        if position:
            query = query.filter(User.preferred_position == position)
        rows = query.order_by(gain_subq.c.gain.desc()).limit(limit).all()
        out = []
        for u, gain_val in rows:
            total_games = (u.games_played or 0) + (u.challenge_wins or 0) + (u.challenge_losses or 0)
            if total_games < 1:
                continue
            out.append(UserSearchResult(
                id=u.id, username=u.username, display_name=u.display_name,
                ai_skill_rating=u.ai_skill_rating, preferred_position=u.preferred_position,
                games_played=u.games_played or 0, wins=u.wins or 0, losses=u.losses or 0,
                challenge_wins=u.challenge_wins or 0, challenge_losses=u.challenge_losses or 0,
                skill_rating_change_week=round(float(gain_val), 2),
            ))
        return out

    # Only rank users who have played at least 1 game (team or 1v1)
    total_games_expr = User.games_played + User.challenge_wins + User.challenge_losses
    query = (
        db.query(User)
        .filter(User.is_disabled == False)
        .filter(total_games_expr >= 1)
    )
    if position:
        query = query.filter(User.preferred_position == position)
    results = query.order_by(User.ai_skill_rating.desc()).limit(limit).all()
    out = []
    for u in results:
        out.append(UserSearchResult(
            id=u.id, username=u.username, display_name=u.display_name,
            ai_skill_rating=u.ai_skill_rating, preferred_position=u.preferred_position,
            games_played=u.games_played or 0, wins=u.wins or 0, losses=u.losses or 0,
            challenge_wins=u.challenge_wins or 0, challenge_losses=u.challenge_losses or 0,
        ))
    return out


@router.get("/users/compare/{user_id}")
def compare_to_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Win probability: P(current user beats target) in 1v1."""
    target = db.query(User).filter(User.id == user_id, User.is_disabled == False).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot compare to yourself")
    from app.ai.win_predictor import predict_1v1_win_probability
    my_win_prob = predict_1v1_win_probability(current_user.ai_skill_rating, target.ai_skill_rating)
    return {
        "target": {"id": target.id, "display_name": target.display_name, "username": target.username, "ai_skill_rating": target.ai_skill_rating},
        "my_win_probability": round(my_win_prob, 2),
        "their_win_probability": round(1 - my_win_prob, 2),
    }


@router.get("/users/{user_id}/challenges-history", response_model=list)
def get_user_challenges_history(
    user_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Public: completed 1v1 challenges for a user (for profile display)."""
    from app.models import Challenge

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    challenges = (
        db.query(Challenge)
        .options(
            joinedload(Challenge.challenger),
            joinedload(Challenge.challenged),
        )
        .filter(
            Challenge.status == "completed",
            or_(
                Challenge.challenger_id == user_id,
                Challenge.challenged_id == user_id,
            ),
        )
        .order_by(Challenge.completed_at.desc().nullslast())
        .limit(limit)
        .all()
    )

    out = []
    for c in challenges:
        out.append({
            "id": c.id,
            "challenger_id": c.challenger_id,
            "challenged_id": c.challenged_id,
            "challenger_name": c.challenger.display_name if c.challenger else None,
            "challenged_name": c.challenged.display_name if c.challenged else None,
            "challenger_score": c.challenger_score,
            "challenged_score": c.challenged_score,
            "winner_id": c.winner_id,
            "completed_at": to_est_isoformat(c.completed_at) if c.completed_at else None,
        })
    return out


@router.get("/users/{user_id}", response_model=UserPublic)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
