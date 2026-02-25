from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, Game, GameParticipant, PlayerGameStats, SkillHistory
from app.schemas import (
    BulkStatsSubmit, PlayerStatsOut, CareerStats, CareerStatsByTypeOut,
    CareerStatsByGameType, GameStatsHistoryEntry, SkillHistoryEntry,
)
from app.auth import get_current_user

router = APIRouter(prefix="/api", tags=["stats"])


@router.post("/games/{game_id}/stats", response_model=list[PlayerStatsOut], status_code=status.HTTP_201_CREATED)
def submit_stats(
    game_id: int,
    data: BulkStatsSubmit,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.status not in ("in_progress", "completed"):
        raise HTTPException(status_code=400, detail="Stats can only be submitted for in-progress or completed games")
    if game.stats_finalized:
        raise HTTPException(status_code=400, detail="Stats have been finalized and can no longer be modified")

    participant_ids = {
        p.user_id
        for p in db.query(GameParticipant).filter(GameParticipant.game_id == game_id).all()
    }

    is_participant = current_user.id in participant_ids
    is_creator = game.creator_id == current_user.id
    is_scorekeeper = game.scorekeeper_id == current_user.id
    if not is_participant and not is_creator and not is_scorekeeper:
        raise HTTPException(status_code=403, detail="Only participants, the creator, or the scorekeeper can submit stats")

    created = []
    for s in data.stats:
        if s.user_id not in participant_ids:
            raise HTTPException(
                status_code=400,
                detail=f"User {s.user_id} is not a participant in this game",
            )

        existing = (
            db.query(PlayerGameStats)
            .filter(PlayerGameStats.game_id == game_id, PlayerGameStats.user_id == s.user_id)
            .first()
        )
        if existing:
            for field in ("pts", "reb", "ast", "stl", "blk", "tov", "fgm", "fga", "three_pm", "three_pa", "ftm", "fta"):
                setattr(existing, field, getattr(s, field))
            created.append(existing)
        else:
            stat = PlayerGameStats(
                user_id=s.user_id,
                game_id=game_id,
                pts=s.pts, reb=s.reb, ast=s.ast,
                stl=s.stl, blk=s.blk, tov=s.tov,
                fgm=s.fgm, fga=s.fga,
                three_pm=s.three_pm, three_pa=s.three_pa,
                ftm=s.ftm, fta=s.fta,
            )
            db.add(stat)
            created.append(stat)

    db.commit()
    for c in created:
        db.refresh(c)
    return created


@router.get("/games/{game_id}/stats", response_model=list[PlayerStatsOut])
def get_game_stats(game_id: int, db: Session = Depends(get_db)):
    stats = db.query(PlayerGameStats).filter(PlayerGameStats.game_id == game_id).all()
    return stats


@router.get("/users/{user_id}/stats", response_model=CareerStats)
def get_career_stats(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    all_stats = db.query(PlayerGameStats).filter(PlayerGameStats.user_id == user_id).all()
    n = len(all_stats)

    if n == 0:
        return CareerStats(
            games_played=user.games_played, wins=user.wins, losses=user.losses,
            win_rate=0.0,
            challenge_wins=user.challenge_wins, challenge_losses=user.challenge_losses,
            ppg=0.0, rpg=0.0, apg=0.0, spg=0.0, bpg=0.0, topg=0.0,
            fg_pct=0.0, three_pct=0.0, ft_pct=0.0,
            total_pts=0, total_reb=0, total_ast=0, total_stl=0, total_blk=0, total_tov=0,
        )

    totals = {
        "pts": sum(s.pts for s in all_stats),
        "reb": sum(s.reb for s in all_stats),
        "ast": sum(s.ast for s in all_stats),
        "stl": sum(s.stl for s in all_stats),
        "blk": sum(s.blk for s in all_stats),
        "tov": sum(s.tov for s in all_stats),
        "fgm": sum(s.fgm for s in all_stats),
        "fga": sum(s.fga for s in all_stats),
        "three_pm": sum(s.three_pm for s in all_stats),
        "three_pa": sum(s.three_pa for s in all_stats),
        "ftm": sum(s.ftm for s in all_stats),
        "fta": sum(s.fta for s in all_stats),
    }

    win_rate = user.wins / user.games_played if user.games_played > 0 else 0.0
    fg_pct = totals["fgm"] / totals["fga"] if totals["fga"] > 0 else 0.0
    three_pct = totals["three_pm"] / totals["three_pa"] if totals["three_pa"] > 0 else 0.0
    ft_pct = totals["ftm"] / totals["fta"] if totals["fta"] > 0 else 0.0

    return CareerStats(
        games_played=user.games_played,
        wins=user.wins,
        losses=user.losses,
        win_rate=round(win_rate, 3),
        challenge_wins=user.challenge_wins,
        challenge_losses=user.challenge_losses,
        ppg=round(totals["pts"] / n, 1),
        rpg=round(totals["reb"] / n, 1),
        apg=round(totals["ast"] / n, 1),
        spg=round(totals["stl"] / n, 1),
        bpg=round(totals["blk"] / n, 1),
        topg=round(totals["tov"] / n, 1),
        fg_pct=round(fg_pct, 3),
        three_pct=round(three_pct, 3),
        ft_pct=round(ft_pct, 3),
        total_pts=totals["pts"],
        total_reb=totals["reb"],
        total_ast=totals["ast"],
        total_stl=totals["stl"],
        total_blk=totals["blk"],
        total_tov=totals["tov"],
    )


@router.get("/users/{user_id}/stats/history", response_model=list[GameStatsHistoryEntry])
def get_stats_history(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = (
        db.query(PlayerGameStats)
        .options(joinedload(PlayerGameStats.game))
        .filter(PlayerGameStats.user_id == user_id)
        .all()
    )

    skill_changes = {
        sh.game_id: sh
        for sh in db.query(SkillHistory).filter(
            SkillHistory.user_id == user_id,
            SkillHistory.game_id.isnot(None),
        ).all()
    }

    result = []
    for s in stats:
        sh = skill_changes.get(s.game_id)
        result.append(GameStatsHistoryEntry(
            game_id=s.game_id,
            game_type=s.game.game_type if s.game else "5v5",
            scheduled_time=s.game.scheduled_time if s.game else s.game_id,
            pts=s.pts, reb=s.reb, ast=s.ast,
            stl=s.stl, blk=s.blk, tov=s.tov,
            fgm=s.fgm, fga=s.fga,
            three_pm=s.three_pm, three_pa=s.three_pa,
            ftm=s.ftm, fta=s.fta,
            skill_before=sh.old_rating if sh else None,
            skill_after=sh.new_rating if sh else None,
        ))

    return result


def _empty_game_type_stats() -> CareerStatsByGameType:
    return CareerStatsByGameType(
        games_played=0,
        ppg=0.0, rpg=0.0, apg=0.0, spg=0.0, bpg=0.0, topg=0.0,
        fg_pct=0.0, three_pct=0.0, ft_pct=0.0,
    )


@router.get("/users/{user_id}/stats/by-game-type", response_model=CareerStatsByTypeOut)
def get_career_stats_by_game_type(user_id: int, db: Session = Depends(get_db)):
    """Career averages split by 5v5, 3v3, 2v2."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats_with_game = (
        db.query(PlayerGameStats, Game.game_type)
        .join(Game, PlayerGameStats.game_id == Game.id)
        .filter(PlayerGameStats.user_id == user_id)
        .all()
    )

    by_type: dict[str, list[PlayerGameStats]] = {"5v5": [], "3v3": [], "2v2": []}
    for s, gt in stats_with_game:
        if gt in by_type:
            by_type[gt].append(s)

    def compute(stats_list: list) -> CareerStatsByGameType:
        n = len(stats_list)
        if n == 0:
            return _empty_game_type_stats()
        totals = {
            "pts": sum(s.pts for s in stats_list),
            "reb": sum(s.reb for s in stats_list),
            "ast": sum(s.ast for s in stats_list),
            "stl": sum(s.stl for s in stats_list),
            "blk": sum(s.blk for s in stats_list),
            "tov": sum(s.tov for s in stats_list),
            "fgm": sum(s.fgm for s in stats_list),
            "fga": sum(s.fga for s in stats_list),
            "three_pm": sum(s.three_pm for s in stats_list),
            "three_pa": sum(s.three_pa for s in stats_list),
            "ftm": sum(s.ftm for s in stats_list),
            "fta": sum(s.fta for s in stats_list),
        }
        fg_pct = totals["fgm"] / totals["fga"] if totals["fga"] > 0 else 0.0
        three_pct = totals["three_pm"] / totals["three_pa"] if totals["three_pa"] > 0 else 0.0
        ft_pct = totals["ftm"] / totals["fta"] if totals["fta"] > 0 else 0.0
        return CareerStatsByGameType(
            games_played=n,
            ppg=round(totals["pts"] / n, 1),
            rpg=round(totals["reb"] / n, 1),
            apg=round(totals["ast"] / n, 1),
            spg=round(totals["stl"] / n, 1),
            bpg=round(totals["blk"] / n, 1),
            topg=round(totals["tov"] / n, 1),
            fg_pct=round(fg_pct, 3),
            three_pct=round(three_pct, 3),
            ft_pct=round(ft_pct, 3),
        )

    return CareerStatsByTypeOut(
        five_v_five=compute(by_type["5v5"]),
        three_v_three=compute(by_type["3v3"]),
        two_v_two=compute(by_type["2v2"]),
    )


@router.get("/users/{user_id}/skill-history", response_model=list[SkillHistoryEntry])
def get_skill_history(user_id: int, db: Session = Depends(get_db)):
    """Skill rating progression over time (for charts)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    entries = (
        db.query(SkillHistory)
        .filter(SkillHistory.user_id == user_id)
        .order_by(SkillHistory.timestamp.asc())
        .all()
    )

    result = []
    for e in entries:
        result.append(SkillHistoryEntry(timestamp=e.timestamp, rating=e.new_rating))

    # Always return at least one point so progression chart can render (current rating)
    if not result:
        ts = user.created_at if user.created_at else datetime.now(timezone.utc)
        result.append(SkillHistoryEntry(timestamp=ts, rating=user.ai_skill_rating or 5.0))

    return result
