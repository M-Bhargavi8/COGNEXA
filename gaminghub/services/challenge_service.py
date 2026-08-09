import json
import random
from datetime import date

from sqlalchemy.exc import IntegrityError

from gaminghub.database.database import db
from gaminghub.models.challenge import Challenge
from gaminghub.models.user_challenge import UserChallenge
from gaminghub.models.game import Game
from gaminghub.config.constants import CHALLENGE_TEMPLATES
from gaminghub.services.reward_service import award


def get_today_challenge():
    """
    Returns today's challenge, creating it on the first call of the day.
    Every later call the same day returns that same row -- refreshing
    the page never rerolls it.
    """

    today = date.today()

    challenge = Challenge.query.filter_by(challenge_date=today).first()

    if challenge:
        return challenge

    template = random.choice(CHALLENGE_TEMPLATES)
    game = Game.query.filter_by(slug=template["game_slug"]).first()

    if not game:
        return None

    challenge = Challenge(
        challenge_date=today,
        game_id=game.id,
        difficulty=template.get("difficulty"),
        description=template["description"],
        criteria=json.dumps(template["criteria"]),
        xp_reward=template["xp"],
        coin_reward=template["coins"]
    )

    db.session.add(challenge)

    try:
        db.session.commit()
    except IntegrityError:
        # Lost a race with another request creating today's challenge first.
        db.session.rollback()
        challenge = Challenge.query.filter_by(challenge_date=today).first()

    return challenge


def has_completed_today(user):
    challenge = get_today_challenge()

    if not challenge:
        return False

    return UserChallenge.query.filter_by(
        user_id=user.id,
        challenge_id=challenge.id
    ).first() is not None


def _meets_criteria(game_result, criteria):
    ctype = criteria.get("type")

    if ctype == "win":
        return game_result.result == "win"

    if ctype == "score_at_least":
        return game_result.score is not None and game_result.score >= criteria["value"]

    if ctype == "duration_under":
        return game_result.duration is not None and game_result.duration <= criteria["value"]

    return False


def check_challenge_completion(user, game_result):
    """Returns today's Challenge if this result just completed it, None otherwise."""

    challenge = get_today_challenge()

    if not challenge or challenge.game_id != game_result.game_id:
        return None

    if challenge.difficulty and game_result.difficulty != challenge.difficulty:
        return None

    already = UserChallenge.query.filter_by(
        user_id=user.id,
        challenge_id=challenge.id
    ).first()

    if already:
        return None

    if not _meets_criteria(game_result, json.loads(challenge.criteria)):
        return None

    db.session.add(UserChallenge(
        user_id=user.id,
        challenge_id=challenge.id,
        game_result_id=game_result.id
    ))

    award(user, xp=challenge.xp_reward, coins=challenge.coin_reward)

    return challenge
