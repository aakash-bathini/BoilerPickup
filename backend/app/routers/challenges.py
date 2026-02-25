"""
1v1 Challenge system — issued via DM, tracked separately from team games.
Affects skill rating (win/loss only, no stats). Both must confirm score.
Flagging for consistent non-confirmation.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.time_utils import to_utc
from app.models import User, Challenge, Block, SkillHistory
from app.schemas import ChallengeCreate, ChallengeScoreSubmit, ChallengeOut
from app.auth import get_current_user
from app.ai.rating import compute_confidence

router = APIRouter(prefix="/api/challenges", tags=["challenges"])

UNCONFIRMED_FLAG_THRESHOLD = 3


def _challenge_to_out(c: Challenge) -> ChallengeOut:
    challenger_win_prob = None
    if c.challenger and c.challenged:
        from app.ai.win_predictor import predict_1v1_win_probability
        challenger_win_prob = round(
            predict_1v1_win_probability(c.challenger.ai_skill_rating, c.challenged.ai_skill_rating), 2
        )
    return ChallengeOut(
        id=c.id,
        challenger_id=c.challenger_id,
        challenged_id=c.challenged_id,
        status=c.status,
        scheduled_time=c.scheduled_time,
        message=c.message,
        challenger_score=c.challenger_score,
        challenged_score=c.challenged_score,
        challenger_confirmed=c.challenger_confirmed,
        challenged_confirmed=c.challenged_confirmed,
        winner_id=c.winner_id,
        created_at=c.created_at,
        completed_at=c.completed_at,
        challenger_name=c.challenger.display_name if c.challenger else None,
        challenged_name=c.challenged.display_name if c.challenged else None,
        challenger_win_probability=challenger_win_prob,
    )


@router.post("", response_model=ChallengeOut, status_code=status.HTTP_201_CREATED)
def create_challenge(
    data: ChallengeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Your account is disabled")
    if data.challenged_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot challenge yourself")

    target = db.query(User).filter(User.id == data.challenged_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.is_disabled:
        raise HTTPException(status_code=400, detail="That user's account is disabled")

    block = (
        db.query(Block)
        .filter(
            or_(
                (Block.blocker_id == current_user.id) & (Block.blocked_id == data.challenged_id),
                (Block.blocker_id == data.challenged_id) & (Block.blocked_id == current_user.id),
            )
        )
        .first()
    )
    if block:
        raise HTTPException(status_code=403, detail="Cannot challenge a blocked user")

    pending = (
        db.query(Challenge)
        .filter(
            Challenge.status.in_(["pending", "accepted", "in_progress", "awaiting_confirmation"]),
            or_(
                (Challenge.challenger_id == current_user.id) & (Challenge.challenged_id == data.challenged_id),
                (Challenge.challenger_id == data.challenged_id) & (Challenge.challenged_id == current_user.id),
            ),
        )
        .first()
    )
    if pending:
        raise HTTPException(status_code=400, detail="You already have an active challenge with this user")

    challenge = Challenge(
        challenger_id=current_user.id,
        challenged_id=data.challenged_id,
        scheduled_time=to_utc(data.scheduled_time),
        message=data.message,
        status="pending",
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    return _challenge_to_out(challenge)


@router.post("/{challenge_id}/accept", response_model=ChallengeOut)
def accept_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if c.challenged_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the challenged user can accept")
    if c.status != "pending":
        raise HTTPException(status_code=400, detail="Challenge is not pending")

    c.status = "accepted"
    db.commit()
    db.refresh(c)
    return _challenge_to_out(c)


@router.post("/{challenge_id}/decline", response_model=ChallengeOut)
def decline_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if c.challenged_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the challenged user can decline")
    if c.status != "pending":
        raise HTTPException(status_code=400, detail="Challenge is not pending")

    c.status = "declined"
    db.commit()
    db.refresh(c)
    return _challenge_to_out(c)


@router.post("/{challenge_id}/submit-score", response_model=ChallengeOut)
def submit_score(
    challenge_id: int,
    data: ChallengeScoreSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if current_user.id not in (c.challenger_id, c.challenged_id):
        raise HTTPException(status_code=403, detail="Not a participant in this challenge")
    if c.status not in ("accepted", "in_progress", "awaiting_confirmation"):
        raise HTTPException(status_code=400, detail="Challenge is not in a valid state for score submission")

    is_challenger = current_user.id == c.challenger_id

    if is_challenger:
        c.challenger_score = data.my_score
        c.challenged_score = data.opponent_score
        c.challenger_confirmed = True
    else:
        c.challenged_score = data.my_score
        c.challenger_score = data.opponent_score
        c.challenged_confirmed = True

    c.status = "awaiting_confirmation"

    if c.challenger_confirmed and c.challenged_confirmed:
        _finalize_challenge(db, c)

    db.commit()
    db.refresh(c)
    return _challenge_to_out(c)


@router.post("/{challenge_id}/confirm", response_model=ChallengeOut)
def confirm_score(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if current_user.id not in (c.challenger_id, c.challenged_id):
        raise HTTPException(status_code=403, detail="Not a participant")
    if c.status != "awaiting_confirmation":
        raise HTTPException(status_code=400, detail="No score to confirm")

    if current_user.id == c.challenger_id:
        c.challenger_confirmed = True
    else:
        c.challenged_confirmed = True

    if c.challenger_confirmed and c.challenged_confirmed:
        _finalize_challenge(db, c)

    db.commit()
    db.refresh(c)
    return _challenge_to_out(c)


def _finalize_challenge(db: Session, c: Challenge):
    """Apply Elo-style rating changes for a completed 1v1.
    
    Uses expected outcome (logistic model) and score-margin amplifier.
    Games are to 15, so margin matters: a 15-0 win is more decisive than 15-14.
    K-factor decays with experience (new players adjust faster).
    """
    import math

    c.status = "completed"
    c.completed_at = datetime.now(timezone.utc)

    if c.challenger_score is None or c.challenged_score is None:
        return

    if c.challenger_score > c.challenged_score:
        c.winner_id = c.challenger_id
        winner = db.query(User).filter(User.id == c.challenger_id).first()
        loser = db.query(User).filter(User.id == c.challenged_id).first()
        w_score, l_score = c.challenger_score, c.challenged_score
    elif c.challenged_score > c.challenger_score:
        c.winner_id = c.challenged_id
        winner = db.query(User).filter(User.id == c.challenged_id).first()
        loser = db.query(User).filter(User.id == c.challenger_id).first()
        w_score, l_score = c.challenged_score, c.challenger_score
    else:
        return

    if winner and loser:
        winner.challenge_wins += 1
        loser.challenge_losses += 1

        # First game: discard self-report — use opponent's rating as prior (self-report only for matching)
        w_total_before = winner.games_played + winner.challenge_wins + winner.challenge_losses - 1
        l_total_before = loser.games_played + loser.challenge_wins + loser.challenge_losses - 1
        w_total_before = max(0, w_total_before)
        l_total_before = max(0, l_total_before)

        w_old = loser.ai_skill_rating if w_total_before == 0 else winner.ai_skill_rating
        l_old = winner.ai_skill_rating if l_total_before == 0 else loser.ai_skill_rating

        # Elo expected outcomes (logistic, scale to 1-10 range with divisor 4)
        expected_w = 1.0 / (1.0 + 10.0 ** ((l_old - w_old) / 4.0))
        expected_l = 1.0 - expected_w

        # K-factor: 1v1 matters more than team — use higher base. Decay with experience.
        k_w = max(0.35, 0.6 / (1.0 + 0.08 * max(0, w_total_before)))
        k_l = max(0.35, 0.6 / (1.0 + 0.08 * max(0, l_total_before)))
        if w_total_before < 3:
            k_w = min(k_w, 0.45)  # Cap first few games
        if l_total_before < 3:
            k_l = min(k_l, 0.45)

        # Score margin (games to 15): 15-0 >> 15-14. Non-linear. Cap for first game.
        margin = w_score - l_score
        margin_mult = 1.0 + min(0.6, (margin / 15.0) ** 0.7)
        if w_total_before < 2 and l_total_before < 2:
            margin_mult = min(margin_mult, 1.3)  # First game: don't let 15-0 push rating too far

        w_change = k_w * (1.0 - expected_w) * margin_mult
        l_change = k_l * (0.0 - expected_l) * margin_mult

        winner.ai_skill_rating = round(min(10.0, max(1.0, w_old + w_change)), 2)
        loser.ai_skill_rating = round(min(10.0, max(1.0, l_old + l_change)), 2)

        w_total = winner.games_played + winner.challenge_wins + winner.challenge_losses
        l_total = loser.games_played + loser.challenge_wins + loser.challenge_losses
        winner.skill_confidence = compute_confidence(w_total)
        loser.skill_confidence = compute_confidence(l_total)

        for user, old_r in [(winner, w_old), (loser, l_old)]:
            db.add(SkillHistory(
                user_id=user.id,
                challenge_id=c.id,
                old_rating=old_r,
                new_rating=user.ai_skill_rating,
                game_type="1v1",
            ))


@router.get("", response_model=list[ChallengeOut])
def list_my_challenges(
    status_filter: str = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Challenge)
        .options(joinedload(Challenge.challenger), joinedload(Challenge.challenged))
        .filter(
            or_(
                Challenge.challenger_id == current_user.id,
                Challenge.challenged_id == current_user.id,
            )
        )
    )
    if status_filter:
        query = query.filter(Challenge.status == status_filter)
    challenges = query.order_by(Challenge.created_at.desc()).limit(50).all()
    return [_challenge_to_out(c) for c in challenges]


@router.get("/{challenge_id}", response_model=ChallengeOut)
def get_challenge(
    challenge_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    c = (
        db.query(Challenge)
        .options(joinedload(Challenge.challenger), joinedload(Challenge.challenged))
        .filter(Challenge.id == challenge_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if current_user.id not in (c.challenger_id, c.challenged_id):
        raise HTTPException(status_code=403, detail="Not a participant")
    return _challenge_to_out(c)
