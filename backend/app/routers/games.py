from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.time_utils import to_utc
from app.models import (
    User, Game, GameParticipant, StatsContest, ContestVote, Block,
    GameReschedule, GameRescheduleVote, PlayerGameStats,
)
from app.schemas import (
    GameCreate, GameOut, GameParticipantOut, GameComplete,
    ScorekeeperInvite, ContestCreate, ContestVoteIn, ContestOut,
    GameReschedulePropose, GameRescheduleVoteIn, GameRescheduleOut,
    GameUpdate,
)
from app.auth import get_current_user

router = APIRouter(prefix="/api/games", tags=["games"])

GAME_TYPE_MAX_PLAYERS = {"5v5": 10, "3v3": 6, "2v2": 4}
REVIEW_PERIOD_HOURS = 24
STATS_DEADLINE_HOURS = 24
UNFILLED_GAME_DELETE_MINUTES = 15  # Delete unfilled games 15 mins before scheduled time
START_WINDOW_HOURS = 1  # Full games must be started within 1 hour of scheduled time or get deleted + strike


def _add_strike(db: Session, user_id: int) -> None:
    """Add a strike (report_count) to user. Check is_disabled after."""
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.report_count = (user.report_count or 0) + 1
        from app.routers.moderation import STRIKE_DISABLE_THRESHOLD
        if user.report_count >= STRIKE_DISABLE_THRESHOLD:
            user.is_disabled = True


def _cleanup_unfilled_games(db: Session) -> None:
    """Delete games that could not fill 15 mins before scheduled time. No strike."""
    cutoff = datetime.now(timezone.utc) + timedelta(minutes=UNFILLED_GAME_DELETE_MINUTES)
    candidates = (
        db.query(Game)
        .filter(
            Game.scheduled_time <= cutoff,
            Game.status.in_(["open", "full"]),
        )
        .all()
    )
    for game in candidates:
        count = db.query(GameParticipant).filter(GameParticipant.game_id == game.id).count()
        if count < game.max_players:
            db.delete(game)
    db.commit()


def _cleanup_expired_full_games(db: Session) -> None:
    """Delete full games past scheduled_time + 1 hour (not started); add strike to creator."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=START_WINDOW_HOURS)
    candidates = (
        db.query(Game)
        .filter(Game.status == "full", Game.scheduled_time < cutoff)
        .all()
    )
    for game in candidates:
        creator_id = game.creator_id
        db.delete(game)
        _add_strike(db, creator_id)
    db.commit()


def _cleanup_games_without_stats(db: Session) -> None:
    """Delete games with no stats 24h past scheduled_time; add strike to creator."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STATS_DEADLINE_HOURS)
    candidates = (
        db.query(Game)
        .filter(
            Game.scheduled_time < cutoff,
            Game.status.in_(["open", "full", "in_progress", "completed"]),
        )
        .all()
    )
    for game in candidates:
        has_stats = db.query(PlayerGameStats).filter(PlayerGameStats.game_id == game.id).first()
        if not has_stats:
            creator_id = game.creator_id
            db.delete(game)
            _add_strike(db, creator_id)
    db.commit()


def _game_to_out(db: Session, game: Game, skip_predict: bool = False) -> GameOut:
    """Converts a Game model to a GameOut schema with enriched participant data and AI metrics.
    skip_predict=True for list view to avoid 50+ model inferences.
    Deduplicates by user_id to prevent 5/4 or duplicate-in-both-teams display bugs."""
    seen_user_ids = set()
    participants_deduped = []
    for p in game.participants:
        if p.user_id in seen_user_ids:
            continue
        seen_user_ids.add(p.user_id)
        participants_deduped.append(p)
    # Enriched participants
    p_out = []
    for p in participants_deduped:
        po = GameParticipantOut.model_validate(p)
        u = p.user
        if u:
            po.username = u.username
            po.display_name = u.display_name
            po.ai_skill_rating = u.ai_skill_rating
            po.preferred_position = u.preferred_position
        p_out.append(po)

    # 1. Calculate prediction and betting lines
    from app.ai.win_predictor import predict_win_probability, calculate_betting_lines
    team_a_parts = [p for p in participants_deduped if p.team == "A"]
    team_b_parts = [p for p in participants_deduped if p.team == "B"]
    
    prob = None
    moneyline = None
    spread = None
    
    # Prediction only valid if roster is full OR game is in progress (skip for list view for speed)
    if not skip_predict and (game.status in ("full", "in_progress", "completed") and 
        len(participants_deduped) >= game.max_players and 
        team_a_parts and team_b_parts):
        try:
            prob = predict_win_probability(db, game, team_a_parts, team_b_parts)
            lines = calculate_betting_lines(prob)
            moneyline = lines["moneyline"]
            spread = lines["spread"]
        except Exception:
            pass
            
    res = GameOut.model_validate(game)
    res.participants = p_out
    # Ensure participant count never exceeds max_players for display
    if len(p_out) > game.max_players:
        res.participants = p_out[: game.max_players]
    res.creator_name = game.creator.display_name if game.creator else "Unknown"
    if game.scorekeeper:
        res.scorekeeper_name = game.scorekeeper.display_name
    
    res.win_prediction = prob
    res.win_line_moneyline = moneyline
    res.win_line_spread = spread
    
    return res


def _load_game(db: Session, game_id: int) -> Game:
    game = (
        db.query(Game)
        .options(joinedload(Game.participants).joinedload(GameParticipant.user))
        .options(joinedload(Game.creator))
        .options(joinedload(Game.scorekeeper))
        .filter(Game.id == game_id)
        .first()
    )
    return game


@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_game(
    data: GameCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Your account is disabled")

    max_players = GAME_TYPE_MAX_PLAYERS[data.game_type]
    court = "fullcourt" if data.game_type == "5v5" else data.court_type

    game = Game(
        creator_id=current_user.id,
        game_type=data.game_type,
        scheduled_time=to_utc(data.scheduled_time),
        skill_min=data.skill_min,
        skill_max=data.skill_max,
        court_type=court,
        max_players=max_players,
        notes=data.notes,
    )
    db.add(game)
    db.flush()

    participant = GameParticipant(user_id=current_user.id, game_id=game.id, team="unassigned")
    db.add(participant)
    db.commit()

    return _game_to_out(db, _load_game(db, game.id))


@router.get("", response_model=list[GameOut])
def list_games(
    game_type: str = Query(None, pattern=r"^(5v5|3v3|2v2)$"),
    status_filter: str = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    blocked_ids = _get_blocked_ids(db, current_user.id)

    _cleanup_unfilled_games(db)
    _cleanup_expired_full_games(db)
    _cleanup_games_without_stats(db)

    query = (
        db.query(Game)
        .options(joinedload(Game.participants).joinedload(GameParticipant.user))
        .options(joinedload(Game.creator))
        .options(joinedload(Game.scorekeeper))
    )

    if game_type:
        query = query.filter(Game.game_type == game_type)
    if status_filter:
        query = query.filter(Game.status == status_filter)
    else:
        query = query.filter(Game.status.in_(["open", "full", "in_progress", "completed"]))

    if blocked_ids:
        query = query.filter(~Game.creator_id.in_(blocked_ids))

    user_skill = current_user.ai_skill_rating
    query = query.filter(Game.skill_min <= user_skill + 1.0, Game.skill_max >= user_skill - 1.0)

    games = query.order_by(Game.scheduled_time.desc()).limit(50).all()
    return [_game_to_out(db, g, skip_predict=True) for g in games]


@router.get("/{game_id}", response_model=GameOut)
def get_game(game_id: int, db: Session = Depends(get_db)):
    _cleanup_unfilled_games(db)
    _cleanup_expired_full_games(db)
    game = _load_game(db, game_id)
    if game and game.status == "in_progress":
        unassigned = [p for p in game.participants if (p.team or "").lower() not in ("a", "b")]
        if unassigned:
            participants = (
                db.query(GameParticipant)
                .options(joinedload(GameParticipant.user))
                .filter(GameParticipant.game_id == game_id)
                .all()
            )
            _fallback_team_assignment(participants)
            db.commit()
            game = _load_game(db, game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return _game_to_out(db, game)


@router.delete("/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creator can delete a game that hasn't started. Strike only if others had joined."""
    game = (
        db.query(Game)
        .options(joinedload(Game.participants))
        .filter(Game.id == game_id)
        .first()
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete the game")
    if game.status not in ("open", "full"):
        raise HTTPException(status_code=400, detail="Cannot delete a game that has started or completed")
    participant_count = len(game.participants)
    db.delete(game)
    if participant_count > 1:
        _add_strike(db, current_user.id)
    db.commit()
    return None


@router.patch("/{game_id}", response_model=GameOut)
def update_game(
    game_id: int,
    data: GameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creator can edit game when no one else has joined. Otherwise use propose reschedule."""
    game = (
        db.query(Game)
        .options(joinedload(Game.participants))
        .options(joinedload(Game.creator))
        .options(joinedload(Game.scorekeeper))
        .filter(Game.id == game_id)
        .first()
    )
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can edit the game")
    if game.status not in ("open", "full"):
        raise HTTPException(status_code=400, detail="Cannot edit a game that has started or completed")
    participant_count = len(game.participants)
    if participant_count > 1:
        raise HTTPException(
            status_code=400,
            detail="Others have joined. Use propose reschedule instead of editing.",
        )
    update_data = data.model_dump(exclude_unset=True)
    if "scheduled_time" in update_data:
        update_data["scheduled_time"] = to_utc(update_data["scheduled_time"])
    if "skill_max" in update_data and "skill_min" not in update_data:
        if update_data["skill_max"] < game.skill_min:
            raise HTTPException(status_code=400, detail="skill_max must be >= skill_min")
    if "skill_min" in update_data and "skill_max" not in update_data:
        if update_data["skill_min"] > game.skill_max:
            raise HTTPException(status_code=400, detail="skill_min must be <= skill_max")
    for k, v in update_data.items():
        setattr(game, k, v)
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


@router.post("/{game_id}/join", response_model=GameOut)
def join_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_disabled:
        raise HTTPException(status_code=403, detail="Your account is disabled")

    _cleanup_unfilled_games(db)
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status not in ("open",):
        if game.status in ("in_progress", "completed"):
            raise HTTPException(status_code=400, detail="Game has started; no more players can join")
        raise HTTPException(status_code=400, detail="Game is full or not accepting players")

    existing = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You are already in this game")

    blocked_ids = _get_blocked_ids(db, current_user.id)
    if game.creator_id in blocked_ids:
        raise HTTPException(status_code=403, detail="Cannot join this game")

    user_skill = current_user.ai_skill_rating
    if user_skill < game.skill_min or user_skill > game.skill_max:
        raise HTTPException(
            status_code=403,
            detail=f"Your skill rating ({user_skill:.1f}) is outside the allowed range [{game.skill_min:.1f} - {game.skill_max:.1f}]",
        )

    participant = GameParticipant(user_id=current_user.id, game_id=game_id, team="unassigned")
    db.add(participant)
    db.flush()

    participants = (
        db.query(GameParticipant)
        .options(joinedload(GameParticipant.user))
        .filter(GameParticipant.game_id == game_id)
        .all()
    )
    if len(participants) >= game.max_players:
        game.status = "full"
        try:
            from app.ai.matchmaking import assign_teams
            assign_teams(db, game, participants)
        except Exception:
            _fallback_team_assignment(participants)
        unassigned = [p for p in participants if (p.team or "").lower() not in ("a", "b")]
        if unassigned:
            _fallback_team_assignment(participants)

    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


@router.post("/{game_id}/leave", response_model=GameOut)
def leave_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status in ("in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Cannot leave a game that has started or completed")
    if game.creator_id == current_user.id:
        raise HTTPException(status_code=400, detail="Game creator cannot leave — cancel the game instead")

    participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=400, detail="You are not in this game")

    db.delete(participant)
    db.flush()  # Ensure delete is applied before counting
    if game.status == "full":
        game.status = "open"
    # When roster becomes incomplete, reset everyone to "joined" (unassigned) until full again
    _reset_teams_if_incomplete(db, game_id, game.max_players)
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


def _reset_teams_if_incomplete(db: Session, game_id: int, max_players: int) -> None:
    """Reset all participants to unassigned when roster is not full."""
    count = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
    if count < max_players:
        db.query(GameParticipant).filter(GameParticipant.game_id == game_id).update(
            {GameParticipant.team: "unassigned"}, synchronize_session=False
        )


@router.post("/{game_id}/kick/{user_id}", response_model=GameOut)
def kick_player(
    game_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game creator can remove players")
    if game.status in ("in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Cannot remove players from a started or completed game")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot kick yourself")

    participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == user_id)
        .first()
    )
    if not participant:
        raise HTTPException(status_code=404, detail="Player is not in this game")

    db.delete(participant)
    db.flush()
    if game.status == "full":
        game.status = "open"
    _reset_teams_if_incomplete(db, game_id, game.max_players)
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


@router.post("/{game_id}/start", response_model=GameOut)
def start_game(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the game creator can start the game")
    if game.status not in ("open", "full"):
        raise HTTPException(status_code=400, detail="Game cannot be started in its current state")

    now = datetime.now(timezone.utc)
    scheduled = game.scheduled_time.replace(tzinfo=timezone.utc) if game.scheduled_time else now
    window_end = scheduled + timedelta(hours=START_WINDOW_HOURS)

    if now < scheduled:
        raise HTTPException(
            status_code=400,
            detail=f"Game cannot be started yet. Scheduled for {scheduled.strftime('%b %d, %Y at %I:%M %p')}.",
        )
    if now > window_end:
        creator_id = game.creator_id
        db.delete(game)
        _add_strike(db, creator_id)
        db.commit()
        raise HTTPException(
            status_code=410,
            detail="Game expired. It was not started within 1 hour of the scheduled time. A strike has been added.",
        )

    participants = (
        db.query(GameParticipant)
        .options(joinedload(GameParticipant.user))
        .filter(GameParticipant.game_id == game_id)
        .all()
    )
    if len(participants) < game.max_players:
        raise HTTPException(
            status_code=400,
            detail=f"Need {game.max_players} players to start, currently have {len(participants)}",
        )

    # Teams already assigned when roster filled; ensure any stragglers get assigned
    unassigned = [p for p in participants if (p.team or "").lower() not in ("a", "b")]
    if unassigned:
        try:
            from app.ai.matchmaking import assign_teams
            assign_teams(db, game, participants)
        except Exception:
            _fallback_team_assignment(participants)
        unassigned = [p for p in participants if (p.team or "").lower() not in ("a", "b")]
        if unassigned:
            _fallback_team_assignment(participants)

    game.status = "in_progress"
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


def _fallback_team_assignment(participants: list[GameParticipant]):
    sorted_p = sorted(participants, key=lambda p: p.user.ai_skill_rating if p.user else 0, reverse=True)
    team_a_skill = 0.0
    team_b_skill = 0.0
    for p in sorted_p:
        skill = p.user.ai_skill_rating if p.user else 5.0
        if team_a_skill <= team_b_skill:
            p.team = "A"
            team_a_skill += skill
        else:
            p.team = "B"
            team_b_skill += skill


@router.post("/{game_id}/complete", response_model=GameOut)
def complete_game(
    game_id: int,
    data: GameComplete,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    allowed = game.creator_id == current_user.id or game.scorekeeper_id == current_user.id
    if not allowed:
        raise HTTPException(status_code=403, detail="Only the creator or scorekeeper can complete the game")
    if game.status != "in_progress":
        raise HTTPException(status_code=400, detail="Game must be in progress to complete")

    game.team_a_score = data.team_a_score
    game.team_b_score = data.team_b_score
    game.status = "completed"
    game.completed_at = datetime.now(timezone.utc)

    participants = (
        db.query(GameParticipant)
        .options(joinedload(GameParticipant.user))
        .filter(GameParticipant.game_id == game_id)
        .all()
    )

    winning_team = "A" if data.team_a_score > data.team_b_score else "B"
    for p in participants:
        if p.user:
            p.user.games_played += 1
            if p.team == winning_team:
                p.user.wins += 1
            else:
                p.user.losses += 1

    try:
        from app.ai.rating import update_ratings_after_game
        update_ratings_after_game(db, game, participants)
    except Exception:
        pass

    db.commit()
    
    # Background worker: Self-Healing ML Engine
    def _trigger_online_train():
        from app.database import SessionLocal
        from app.ai.win_predictor import online_train
        db_bg = SessionLocal()
        try:
            online_train(db_bg)
        finally:
            db_bg.close()
            
    background_tasks.add_task(_trigger_online_train)
    
    return _game_to_out(db, _load_game(db, game_id))


# ── Scorekeeper ──────────────────────────────

@router.post("/{game_id}/invite-scorekeeper", response_model=GameOut)
def invite_scorekeeper(
    game_id: int,
    data: ScorekeeperInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can invite a scorekeeper")

    is_participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == data.user_id)
        .first()
    )
    if is_participant:
        raise HTTPException(status_code=400, detail="Scorekeeper cannot be a game participant")

    sk = db.query(User).filter(User.id == data.user_id).first()
    if not sk:
        raise HTTPException(status_code=404, detail="User not found")

    game.scorekeeper_id = data.user_id
    game.scorekeeper_status = "pending"
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


@router.post("/{game_id}/accept-scorekeeper", response_model=GameOut)
def accept_scorekeeper(
    game_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.scorekeeper_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the invited scorekeeper")
    if game.scorekeeper_status != "pending":
        raise HTTPException(status_code=400, detail="Invitation is not pending")

    game.scorekeeper_status = "accepted"
    db.commit()
    return _game_to_out(db, _load_game(db, game_id))


@router.get("/scorekeeping/mine", response_model=list[GameOut])
def my_scorekeeping_games(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    games = (
        db.query(Game)
        .options(joinedload(Game.participants).joinedload(GameParticipant.user))
        .options(joinedload(Game.creator))
        .options(joinedload(Game.scorekeeper))
        .filter(Game.scorekeeper_id == current_user.id)
        .order_by(Game.scheduled_time.desc())
        .limit(20)
        .all()
    )
    return [_game_to_out(db, g) for g in games]


# ── Stats Contest ────────────────────────────

@router.post("/{game_id}/contest", response_model=ContestOut, status_code=status.HTTP_201_CREATED)
def create_contest(
    game_id: int,
    data: ContestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status != "completed":
        raise HTTPException(status_code=400, detail="Can only contest completed games")
    if game.stats_finalized:
        raise HTTPException(status_code=400, detail="Stats are already finalized")

    is_participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    if not is_participant and game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only participants or the creator can contest stats")

    if game.completed_at:
        completed = game.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        deadline = completed + timedelta(hours=REVIEW_PERIOD_HOURS)
        if datetime.now(timezone.utc) > deadline:
            raise HTTPException(status_code=400, detail="24-hour review period has expired")

    existing = db.query(StatsContest).filter(
        StatsContest.game_id == game_id, StatsContest.status == "open"
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="There is already an open contest for this game")

    contest = StatsContest(
        game_id=game_id,
        contester_id=current_user.id,
        reason=data.reason,
    )
    db.add(contest)
    db.commit()
    db.refresh(contest)

    return ContestOut(
        id=contest.id, game_id=contest.game_id, contester_id=contest.contester_id,
        reason=contest.reason, status=contest.status,
        votes_for=0, votes_against=0, created_at=contest.created_at,
        contester_name=current_user.display_name,
    )


@router.post("/{game_id}/contest/{contest_id}/vote", response_model=ContestOut)
def vote_on_contest(
    game_id: int,
    contest_id: int,
    data: ContestVoteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contest = db.query(StatsContest).filter(
        StatsContest.id == contest_id, StatsContest.game_id == game_id
    ).first()
    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")
    if contest.status != "open":
        raise HTTPException(status_code=400, detail="Contest is no longer open")

    is_participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    if not is_participant:
        raise HTTPException(status_code=403, detail="Only game participants can vote")

    existing_vote = db.query(ContestVote).filter(
        ContestVote.contest_id == contest_id, ContestVote.voter_id == current_user.id
    ).first()
    if existing_vote:
        raise HTTPException(status_code=400, detail="You have already voted")

    vote = ContestVote(contest_id=contest_id, voter_id=current_user.id, vote=data.support)
    db.add(vote)

    if data.support:
        contest.votes_for += 1
    else:
        contest.votes_against += 1

    total_participants = db.query(GameParticipant).filter(
        GameParticipant.game_id == game_id
    ).count()
    total_votes = contest.votes_for + contest.votes_against

    if contest.votes_for >= (total_participants / 2):
        contest.status = "approved"
        contest.resolved_at = datetime.now(timezone.utc)
    elif contest.votes_against > (total_participants / 2):
        contest.status = "rejected"
        contest.resolved_at = datetime.now(timezone.utc)
    elif total_votes >= total_participants:
        if contest.votes_for >= contest.votes_against:
            contest.status = "approved"
        else:
            contest.status = "rejected"
        contest.resolved_at = datetime.now(timezone.utc)

    db.commit()

    contester = db.query(User).filter(User.id == contest.contester_id).first()
    return ContestOut(
        id=contest.id, game_id=contest.game_id, contester_id=contest.contester_id,
        reason=contest.reason, status=contest.status,
        votes_for=contest.votes_for, votes_against=contest.votes_against,
        created_at=contest.created_at, resolved_at=contest.resolved_at,
        contester_name=contester.display_name if contester else None,
    )


@router.get("/{game_id}/contests", response_model=list[ContestOut])
def list_contests(game_id: int, db: Session = Depends(get_db)):
    contests = db.query(StatsContest).filter(StatsContest.game_id == game_id).all()
    result = []
    for c in contests:
        contester = db.query(User).filter(User.id == c.contester_id).first()
        result.append(ContestOut(
            id=c.id, game_id=c.game_id, contester_id=c.contester_id,
            reason=c.reason, status=c.status,
            votes_for=c.votes_for, votes_against=c.votes_against,
            created_at=c.created_at, resolved_at=c.resolved_at,
            contester_name=contester.display_name if contester else None,
        ))
    return result


# ── Reschedule ──────────────────────────────────────────────────────────────

@router.post("/{game_id}/reschedule", response_model=GameRescheduleOut, status_code=status.HTTP_201_CREATED)
def propose_reschedule(
    game_id: int,
    data: GameReschedulePropose,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creator proposes new time. Only available when others have joined. All participants must vote to approve."""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can propose a reschedule")
    if game.status not in ("open", "full"):
        raise HTTPException(status_code=400, detail="Cannot reschedule a game that has started or completed")
    participant_count = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
    if participant_count <= 1:
        raise HTTPException(
            status_code=400,
            detail="Propose reschedule only when others have joined. Edit the game directly if you're alone.",
        )

    pending = db.query(GameReschedule).filter(
        GameReschedule.game_id == game_id,
        GameReschedule.status == "pending",
    ).first()
    if pending:
        raise HTTPException(status_code=400, detail="There is already a pending reschedule proposal")

    reschedule = GameReschedule(
        game_id=game_id,
        proposed_scheduled_time=to_utc(data.scheduled_time),
        proposed_by_id=current_user.id,
        status="pending",
    )
    db.add(reschedule)
    db.commit()
    db.refresh(reschedule)

    total = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
    return GameRescheduleOut(
        id=reschedule.id,
        game_id=reschedule.game_id,
        proposed_scheduled_time=reschedule.proposed_scheduled_time,
        proposed_by_id=reschedule.proposed_by_id,
        status=reschedule.status,
        votes_for=0,
        votes_against=0,
        total_participants=total,
        created_at=reschedule.created_at,
    )


@router.post("/{game_id}/reschedule/{reschedule_id}/vote", response_model=GameRescheduleOut)
def vote_reschedule(
    game_id: int,
    reschedule_id: int,
    data: GameRescheduleVoteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Participant votes on reschedule. Approved when all vote yes."""
    reschedule = db.query(GameReschedule).filter(
        GameReschedule.id == reschedule_id,
        GameReschedule.game_id == game_id,
    ).first()
    if not reschedule:
        raise HTTPException(status_code=404, detail="Reschedule proposal not found")
    if reschedule.status != "pending":
        raise HTTPException(status_code=400, detail="Reschedule is no longer pending")

    is_participant = (
        db.query(GameParticipant)
        .filter(GameParticipant.game_id == game_id, GameParticipant.user_id == current_user.id)
        .first()
    )
    if not is_participant:
        raise HTTPException(status_code=403, detail="Only participants can vote on reschedule")

    existing = db.query(GameRescheduleVote).filter(
        GameRescheduleVote.reschedule_id == reschedule_id,
        GameRescheduleVote.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You have already voted")

    vote = GameRescheduleVote(reschedule_id=reschedule_id, user_id=current_user.id, approved=data.approved)
    db.add(vote)
    db.commit()

    votes_for = db.query(GameRescheduleVote).filter(
        GameRescheduleVote.reschedule_id == reschedule_id,
        GameRescheduleVote.approved == True,
    ).count()
    votes_against = db.query(GameRescheduleVote).filter(
        GameRescheduleVote.reschedule_id == reschedule_id,
        GameRescheduleVote.approved == False,
    ).count()
    total_participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()

    if votes_against > 0:
        reschedule.status = "rejected"
        db.commit()
    elif votes_for >= total_participants:
        game = db.query(Game).filter(Game.id == game_id).first()
        if game:
            game.scheduled_time = reschedule.proposed_scheduled_time
            reschedule.status = "approved"
            db.commit()

    db.refresh(reschedule)
    return GameRescheduleOut(
        id=reschedule.id,
        game_id=reschedule.game_id,
        proposed_scheduled_time=reschedule.proposed_scheduled_time,
        proposed_by_id=reschedule.proposed_by_id,
        status=reschedule.status,
        votes_for=votes_for,
        votes_against=votes_against,
        total_participants=total_participants,
        created_at=reschedule.created_at,
    )


@router.get("/{game_id}/reschedule", response_model=list[GameRescheduleOut])
def list_reschedule_proposals(game_id: int, db: Session = Depends(get_db)):
    proposals = db.query(GameReschedule).filter(GameReschedule.game_id == game_id).order_by(GameReschedule.created_at.desc()).all()
    total_participants = db.query(GameParticipant).filter(GameParticipant.game_id == game_id).count()
    result = []
    for r in proposals:
        votes_for = db.query(GameRescheduleVote).filter(
            GameRescheduleVote.reschedule_id == r.id,
            GameRescheduleVote.approved == True,
        ).count()
        votes_against = db.query(GameRescheduleVote).filter(
            GameRescheduleVote.reschedule_id == r.id,
            GameRescheduleVote.approved == False,
        ).count()
        result.append(GameRescheduleOut(
            id=r.id,
            game_id=r.game_id,
            proposed_scheduled_time=r.proposed_scheduled_time,
            proposed_by_id=r.proposed_by_id,
            status=r.status,
            votes_for=votes_for,
            votes_against=votes_against,
            total_participants=total_participants,
            created_at=r.created_at,
        ))
    return result


def _get_blocked_ids(db: Session, user_id: int) -> set[int]:
    blocks = db.query(Block).filter(
        or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
    ).all()
    ids = set()
    for b in blocks:
        ids.add(b.blocker_id if b.blocked_id == user_id else b.blocked_id)
    return ids
