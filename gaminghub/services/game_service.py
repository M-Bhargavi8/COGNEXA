import json
import uuid
from datetime import datetime

from flask import url_for

from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.models.game_result import GameResult
from gaminghub.services.reward_service import award
from gaminghub.services import achievement_service
from gaminghub.services import challenge_service
from gaminghub.services import notification_service


GAME_PLAY_ENDPOINTS = {
    "guess-the-number": "games.guess",
    "rock-paper-scissors": "games.rps",
    "tic-tac-toe": "tictactoe.play",
    "memory-matrix": "brain_lab.memory_matrix",
    "reflex-lab": "brain_lab.reflex_lab",
    "focus-shift": "brain_lab.focus_shift",
    "sequence-breaker": "brain_lab.sequence_breaker",
    "code-breaker": "brain_lab.code_breaker",
    "dual-task": "brain_lab.dual_task",
    "risk-reward": "brain_lab.risk_reward",
    "logic-grid": "brain_lab.logic_grid",
}


def get_game(slug):
    return Game.query.filter_by(slug=slug).first()


def get_play_url(slug):
    endpoint = GAME_PLAY_ENDPOINTS.get(slug)
    return url_for(endpoint) if endpoint else None


def get_active_session(user, game):

    return GameSession.query.filter_by(
        user_id=user.id,
        game_id=game.id,
        status="active"
    ).first()


def get_state(session):
    return json.loads(session.state)


def set_state(session, state):

    session.state = json.dumps(state)

    db.session.commit()


def start_session(user, slug, *, difficulty=None, state=None):
    """
    Starts a new session for (user, game), abandoning any existing
    active session for that pair first — a user only ever has at most
    one active session per game.
    """

    game = get_game(slug)

    existing = get_active_session(user, game)

    if existing:
        existing.status = "abandoned"
        existing.ended_at = datetime.utcnow()

    session = GameSession(
        user_id=user.id,
        game_id=game.id,
        difficulty=difficulty,
        state=json.dumps(state or {}),
        status="active",
        session_token=uuid.uuid4().hex,
        started_at=datetime.utcnow()
    )

    db.session.add(session)
    db.session.commit()

    return session


def complete_session(session, user, *, outcome, xp=0, coins=0, score=0,
                      attempts=None, accuracy=None, reaction_time=None,
                      mistakes=None):
    """
    The single place a game session is allowed to turn into a reward.
    Returns None (grants nothing) if the session isn't active, which
    is what makes a resubmitted/replayed POST against an already-
    completed session a no-op instead of a duplicate reward.
    """

    if session.status != "active":
        return None

    session.status = "completed"
    session.ended_at = datetime.utcnow()

    achievements_unlocked = award(user, xp=xp, coins=coins, outcome=outcome)

    duration = (session.ended_at - session.started_at).total_seconds()

    previous_best = db.session.query(
        db.func.max(GameResult.score)
    ).filter_by(
        user_id=session.user_id,
        game_id=session.game_id
    ).scalar()

    result = GameResult(
        user_id=session.user_id,
        game_id=session.game_id,
        game_session_id=session.id,
        difficulty=session.difficulty,
        result=outcome,
        score=score,
        xp_earned=xp,
        coins_earned=coins,
        duration=duration,
        attempts=attempts,
        accuracy=accuracy,
        reaction_time=reaction_time,
        mistakes=mistakes
    )

    db.session.add(result)
    db.session.commit()

    game_achievements = achievement_service.check_game_achievements(user, result)
    notification_service.notify_achievements(user, game_achievements)
    achievements_unlocked += game_achievements

    challenge_completed = challenge_service.check_challenge_completion(user, result)

    is_new_best = previous_best is not None and score > previous_best

    game = Game.query.get(session.game_id)

    if is_new_best:
        notification_service.create(
            user, "personal_best", f"New Personal Best in {game.name}!",
            message=f"Score: {score}", icon="🎯", link=get_play_url(game.slug)
        )

    if challenge_completed:
        notification_service.create(
            user, "challenge", "Daily Challenge Complete!",
            message=challenge_completed.description, icon="🔥", link="/dashboard"
        )

    return {
        "result": result,
        "is_new_best": is_new_best,
        "achievements_unlocked": achievements_unlocked,
        "challenge_completed": challenge_completed
    }


def get_current_streak(user, game):
    """Consecutive wins for (user, game), most recent first."""

    recent = GameResult.query.filter_by(
        user_id=user.id,
        game_id=game.id
    ).order_by(GameResult.created_at.desc()).limit(50).all()

    streak = 0

    for r in recent:
        if r.result != "win":
            break
        streak += 1

    return streak


def get_reaction_stats(user, game):
    results = GameResult.query.filter(
        GameResult.user_id == user.id,
        GameResult.game_id == game.id,
        GameResult.reaction_time.isnot(None)
    ).all()

    if not results:
        return {"best": None, "average": None, "attempts": 0}

    times = [r.reaction_time for r in results]

    return {
        "best": min(times),
        "average": round(sum(times) / len(times)),
        "attempts": len(times)
    }
