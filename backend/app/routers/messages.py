from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.models import User, Game, GameParticipant, Message, Block
from app.schemas import MessageCreate, MessageOut, ConversationPreview
from app.auth import get_current_user

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _is_blocked(db: Session, user_a: int, user_b: int) -> bool:
    return db.query(Block).filter(
        or_(
            and_(Block.blocker_id == user_a, Block.blocked_id == user_b),
            and_(Block.blocker_id == user_b, Block.blocked_id == user_a),
        )
    ).first() is not None


def _msg_to_out(m: Message, senders: dict) -> MessageOut:
    sender = senders.get(m.sender_id)
    return MessageOut(
        id=m.id,
        sender_id=m.sender_id,
        game_id=m.game_id,
        recipient_id=m.recipient_id,
        content=m.content,
        created_at=m.created_at,
        sender_name=sender.display_name if sender else None,
        sender_username=sender.username if sender else None,
    )


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Your account is disabled")
    if not data.game_id and not data.recipient_id:
        raise HTTPException(status_code=400, detail="Must specify either game_id or recipient_id")
    if data.game_id and data.recipient_id:
        raise HTTPException(status_code=400, detail="Cannot specify both game_id and recipient_id")

    if data.game_id:
        game = db.query(Game).filter(Game.id == data.game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        is_participant = (
            db.query(GameParticipant)
            .filter(GameParticipant.game_id == data.game_id, GameParticipant.user_id == current_user.id)
            .first()
        )
        is_scorekeeper = game.scorekeeper_id == current_user.id
        if not is_participant and not is_scorekeeper:
            raise HTTPException(status_code=403, detail="You must be a participant or scorekeeper to chat in this game")

    if data.recipient_id:
        if data.recipient_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot send a message to yourself")
        recipient = db.query(User).filter(User.id == data.recipient_id).first()
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        if _is_blocked(db, current_user.id, data.recipient_id):
            raise HTTPException(status_code=403, detail="Cannot message this user")

    msg = Message(
        sender_id=current_user.id,
        game_id=data.game_id,
        recipient_id=data.recipient_id,
        content=data.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return MessageOut(
        id=msg.id,
        sender_id=msg.sender_id,
        game_id=msg.game_id,
        recipient_id=msg.recipient_id,
        content=msg.content,
        created_at=msg.created_at,
        sender_name=current_user.display_name,
        sender_username=current_user.username,
    )


@router.get("/game/{game_id}", response_model=list[MessageOut])
def get_game_messages(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    is_participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    is_scorekeeper = game.scorekeeper_id == current_user.id
    if not is_participant and not is_scorekeeper:
        raise HTTPException(status_code=403, detail="You must be a participant or scorekeeper to view game chat")

    messages = (
        db.query(Message)
        .filter(Message.game_id == game_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    sender_ids = {m.sender_id for m in messages}
    senders = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}

    return [_msg_to_out(m, senders) for m in messages]


@router.get("/dm/{user_id}", response_model=list[MessageOut])
def get_dm_thread(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all DMs between the current user and user_id.
    Both directions (sent by me TO them, sent by them TO me) are in the same thread.
    """
    messages = (
        db.query(Message)
        .filter(
            Message.game_id.is_(None),
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == user_id),
                and_(Message.sender_id == user_id, Message.recipient_id == current_user.id),
            ),
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    sender_ids = {m.sender_id for m in messages}
    sender_ids.add(current_user.id)
    sender_ids.add(user_id)
    senders = {u.id: u for u in db.query(User).filter(User.id.in_(sender_ids)).all()} if sender_ids else {}

    return [_msg_to_out(m, senders) for m in messages]


@router.get("/conversations", response_model=list[ConversationPreview])
def get_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    dm_messages = (
        db.query(Message)
        .filter(
            Message.game_id.is_(None),
            or_(
                Message.sender_id == current_user.id,
                Message.recipient_id == current_user.id,
            ),
        )
        .order_by(Message.created_at.desc())
        .all()
    )

    conversations: dict[int, Message] = {}
    for m in dm_messages:
        other_id = m.recipient_id if m.sender_id == current_user.id else m.sender_id
        if other_id and other_id not in conversations:
            conversations[other_id] = m

    other_ids = list(conversations.keys())
    if not other_ids:
        return []

    users_map = {u.id: u for u in db.query(User).filter(User.id.in_(other_ids)).all()}

    result = []
    for uid, msg in conversations.items():
        u = users_map.get(uid)
        if u:
            result.append(ConversationPreview(
                user_id=uid,
                username=u.username,
                display_name=u.display_name,
                last_message=msg.content[:100],
                last_message_time=msg.created_at,
            ))

    return result
