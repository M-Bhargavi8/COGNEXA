import json
from datetime import date

from gaminghub.database.database import db
from gaminghub.services import challenge_service
from gaminghub.models.challenge import Challenge
from gaminghub.models.user_challenge import UserChallenge
from gaminghub.models.game_result import GameResult
from gaminghub.models.game_session import GameSession


def _make_challenge(game, criteria, difficulty=None, xp=50, coins=25):
    challenge = Challenge(
        challenge_date=date.today(), game_id=game.id, difficulty=difficulty,
        description="Test challenge", criteria=json.dumps(criteria),
        xp_reward=xp, coin_reward=coins
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def _make_result(user, game, **kwargs):
    session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
    db.session.add(session)
    db.session.commit()
    defaults = {"result": "win", "score": 0}
    defaults.update(kwargs)
    result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, **defaults)
    db.session.add(result)
    db.session.commit()
    return result


class TestGetTodayChallenge:

    def test_returns_none_without_a_matching_seeded_game(self, app, monkeypatch):
        # challenge_service did `from ...constants import CHALLENGE_TEMPLATES`,
        # which bound its own name in this module's namespace -- patching the
        # constants module itself wouldn't touch that already-bound name, so
        # the patch target has to be challenge_service.CHALLENGE_TEMPLATES.
        monkeypatch.setattr(challenge_service, "CHALLENGE_TEMPLATES", [
            {"game_slug": "nonexistent-slug", "description": "x", "criteria": {"type": "win"}, "xp": 1, "coins": 1}
        ])
        assert challenge_service.get_today_challenge() is None

    def test_creates_once_and_reuses_the_same_row_on_repeat_calls(self, make_game, monkeypatch):
        game = make_game(slug="guess-the-number")
        monkeypatch.setattr(challenge_service, "CHALLENGE_TEMPLATES", [
            {"game_slug": "guess-the-number", "description": "Win it", "criteria": {"type": "win"}, "xp": 10, "coins": 5}
        ])

        first = challenge_service.get_today_challenge()
        second = challenge_service.get_today_challenge()

        assert first.id == second.id
        assert Challenge.query.count() == 1


class TestHasCompletedToday:

    def test_false_when_no_challenge_exists(self, make_user):
        user = make_user()
        assert challenge_service.has_completed_today(user) is False

    def test_false_before_completing_it(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "win"})
        assert challenge_service.has_completed_today(user) is False

    def test_true_after_completing_it(self, make_user, make_game):
        user = make_user()
        game = make_game()
        challenge = _make_challenge(game, {"type": "win"})
        result = _make_result(user, game, result="win")
        db.session.add(UserChallenge(user_id=user.id, challenge_id=challenge.id, game_result_id=result.id))
        db.session.commit()

        assert challenge_service.has_completed_today(user) is True


class TestCheckChallengeCompletion:

    def test_win_criteria_satisfied_by_a_winning_result(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "win"})
        result = _make_result(user, game, result="win")

        completed = challenge_service.check_challenge_completion(user, result)

        assert completed is not None
        assert UserChallenge.query.filter_by(user_id=user.id).count() == 1

    def test_win_criteria_not_satisfied_by_a_loss(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "win"})
        result = _make_result(user, game, result="loss")

        assert challenge_service.check_challenge_completion(user, result) is None

    def test_score_at_least_criteria(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "score_at_least", "value": 50})

        low = _make_result(user, game, score=30)
        assert challenge_service.check_challenge_completion(user, low) is None

        high = _make_result(user, game, score=50)
        assert challenge_service.check_challenge_completion(user, high) is not None

    def test_duration_under_criteria(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "duration_under", "value": 10})

        slow = _make_result(user, game, duration=15)
        assert challenge_service.check_challenge_completion(user, slow) is None

        fast = _make_result(user, game, duration=5)
        assert challenge_service.check_challenge_completion(user, fast) is not None

    def test_wrong_game_never_completes_the_challenge(self, make_user, make_game):
        user = make_user()
        challenge_game = make_game(slug="challenge-game")
        other_game = make_game(slug="other-game")
        _make_challenge(challenge_game, {"type": "win"})

        result = _make_result(user, other_game, result="win")

        assert challenge_service.check_challenge_completion(user, result) is None

    def test_wrong_difficulty_never_completes_the_challenge(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "win"}, difficulty="hard")

        result = _make_result(user, game, result="win", difficulty="easy")

        assert challenge_service.check_challenge_completion(user, result) is None

    def test_completing_twice_only_records_it_once(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _make_challenge(game, {"type": "win"})

        result1 = _make_result(user, game, result="win")
        result2 = _make_result(user, game, result="win")

        first = challenge_service.check_challenge_completion(user, result1)
        second = challenge_service.check_challenge_completion(user, result2)

        assert first is not None
        assert second is None
        assert UserChallenge.query.filter_by(user_id=user.id).count() == 1

    def test_completing_awards_xp_and_coins(self, make_user, make_game):
        user = make_user(coins=0)
        game = make_game()
        _make_challenge(game, {"type": "win"}, xp=40, coins=15)
        result = _make_result(user, game, result="win")

        challenge_service.check_challenge_completion(user, result)

        assert user.xp == 40
        assert user.coins == 15
