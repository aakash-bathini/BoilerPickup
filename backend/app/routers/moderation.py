"""
Report and block system.
- Report: harassment/cheating. 5 unique reports = account disabled.
- Block: mutual invisibility in search/games/messages.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models import User, Block, Report
from app.schemas import ReportCreate, ReportOut, BlockOut
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["moderation"])

STRIKE_DISABLE_THRESHOLD = 10  # report_count + management strikes; 10 total = account disabled


@router.post("/report", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def report_user(
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if data.reported_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot report yourself")

    target = db.query(User).filter(User.id == data.reported_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(Report)
        .filter(Report.reporter_id == current_user.id, Report.reported_id == data.reported_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already reported this user")

    report = Report(
        reporter_id=current_user.id,
        reported_id=data.reported_id,
        reason=data.reason,
        details=data.details,
    )
    db.add(report)

    target.report_count += 1
    if target.report_count >= STRIKE_DISABLE_THRESHOLD:
        target.is_disabled = True

    db.commit()
    db.refresh(report)
    return report


@router.post("/block/{user_id}", response_model=BlockOut, status_code=status.HTTP_201_CREATED)
def block_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        db.query(Block)
        .filter(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already blocked")

    block = Block(blocker_id=current_user.id, blocked_id=user_id)
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.delete("/block/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    block = (
        db.query(Block)
        .filter(Block.blocker_id == current_user.id, Block.blocked_id == user_id)
        .first()
    )
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    db.delete(block)
    db.commit()


@router.get("/blocks", response_model=list[BlockOut])
def list_blocks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    blocks = db.query(Block).filter(Block.blocker_id == current_user.id).all()
    return blocks


def get_blocked_ids(db: Session, user_id: int) -> set[int]:
    """Return all user IDs that should be invisible to this user."""
    blocks = db.query(Block).filter(
        or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
    ).all()
    ids = set()
    for b in blocks:
        ids.add(b.blocker_id if b.blocked_id == user_id else b.blocked_id)
    return ids
