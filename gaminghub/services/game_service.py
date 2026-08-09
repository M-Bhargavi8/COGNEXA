import json
import uuid
from datetime import datetime

from gaminghub.database.database import db
from gaminghub.models.game import Game
from gaminghub.models.game_session import GameSession
from gaminghub.models.game_result import GameResult
from gaminghub.services.reward_service import award


def get_game(slug):
    return Game.query.filter_by(slug=slug).first()


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

    award(user, xp=xp, coins=coins, outcome=outcome)

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

    is_new_best = previous_best is None or score > previous_best

    return {"result": result, "is_new_best": is_new_best}


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
