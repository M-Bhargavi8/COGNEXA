import json

from gaminghub.database.database import db as _db
from gaminghub.services import game_service


class TestStartSession:

    def test_creates_an_active_session(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")
            assert session.status == "active"
            assert session.user_id == user.id

    def test_abandons_a_prior_active_session_for_the_same_game(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            first = game_service.start_session(user, "test-game")
            second = game_service.start_session(user, "test-game")

            assert first.status == "abandoned"
            assert first.ended_at is not None
            assert second.status == "active"
            assert second.id != first.id

    def test_stores_initial_state_as_json(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game", state={"secret": 42})
            assert json.loads(session.state) == {"secret": 42}


class TestCompleteSessionAntiCheat:
    """
    The chokepoint that makes replay/double-submission a no-op instead of
    a duplicate reward -- this is the property the Phase 2 tic-tac-toe
    board-injection fix and every game route since then depends on.
    """

    def test_rejects_a_session_that_is_not_active(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")
            session.status = "abandoned"

            result = game_service.complete_session(session, user, outcome="win", xp=100, coins=100, score=100)

            assert result is None

    def test_replaying_an_already_completed_session_grants_nothing_twice(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")

            first = game_service.complete_session(session, user, outcome="win", xp=50, coins=50, score=10)
            assert first is not None
            xp_after_first = user.xp
            coins_after_first = user.coins

            # replaying the exact same (now-completed) session
            second = game_service.complete_session(session, user, outcome="win", xp=50, coins=50, score=10)

            assert second is None
            assert user.xp == xp_after_first
            assert user.coins == coins_after_first

    def test_completing_marks_the_session_completed(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")
            game_service.complete_session(session, user, outcome="win", xp=10, coins=10, score=5)
            assert session.status == "completed"
            assert session.ended_at is not None

    def test_completing_creates_a_game_result(self, app, make_user, make_game):
        with app.test_request_context():
            from gaminghub.models.game_result import GameResult

            user = make_user()
            game = make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")
            result = game_service.complete_session(session, user, outcome="win", xp=10, coins=10, score=7)

            row = _db.session.get(GameResult, result["result"].id)
            assert row.user_id == user.id
            assert row.game_id == game.id
            assert row.score == 7
            assert row.result == "win"


class TestIsNewBest:
    """The is_new_best bug fixed in Phase 4: previous_best is None on a
    first-ever play, which must not be treated as "beating a best of
    nothing" -- there's nothing to beat yet."""

    def test_first_ever_play_is_not_a_new_best(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game")
            result = game_service.complete_session(session, user, outcome="win", xp=1, coins=1, score=50)
            assert result["is_new_best"] is False

    def test_a_higher_second_score_is_a_new_best(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")

            s1 = game_service.start_session(user, "test-game")
            game_service.complete_session(s1, user, outcome="win", xp=1, coins=1, score=50)

            s2 = game_service.start_session(user, "test-game")
            result = game_service.complete_session(s2, user, outcome="win", xp=1, coins=1, score=80)

            assert result["is_new_best"] is True

    def test_a_lower_second_score_is_not_a_new_best(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")

            s1 = game_service.start_session(user, "test-game")
            game_service.complete_session(s1, user, outcome="win", xp=1, coins=1, score=80)

            s2 = game_service.start_session(user, "test-game")
            result = game_service.complete_session(s2, user, outcome="win", xp=1, coins=1, score=50)

            assert result["is_new_best"] is False


class TestStateHelpers:

    def test_get_state_and_set_state_roundtrip(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")
            session = game_service.start_session(user, "test-game", state={"a": 1})

            game_service.set_state(session, {"a": 2, "b": 3})

            assert game_service.get_state(session) == {"a": 2, "b": 3}


class TestGetPlayUrl:

    def test_known_slug_returns_a_url(self, app):
        with app.test_request_context():
            url = game_service.get_play_url("guess-the-number")
            assert url == "/guess"

    def test_unknown_slug_returns_none(self, app):
        with app.test_request_context():
            assert game_service.get_play_url("not-a-real-game") is None


class TestStreakAndReactionStats:

    def test_current_streak_counts_consecutive_wins_from_most_recent(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")

            outcomes = ["loss", "win", "win", "win"]  # most recent first once created in order
            for outcome in outcomes:
                session = game_service.start_session(user, "test-game")
                game_service.complete_session(session, user, outcome=outcome, xp=1, coins=1, score=1)

            game = game_service.get_game("test-game")
            assert game_service.get_current_streak(user, game) == 3

    def test_reaction_stats_with_no_data(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            game = make_game(slug="test-game")
            stats = game_service.get_reaction_stats(user, game)
            assert stats == {"best": None, "average": None, "attempts": 0}

    def test_reaction_stats_with_data(self, app, make_user, make_game):
        with app.test_request_context():
            user = make_user()
            make_game(slug="test-game")

            for rt in [300, 200, 250]:
                session = game_service.start_session(user, "test-game")
                game_service.complete_session(session, user, outcome="win", xp=1, coins=1, score=1, reaction_time=rt)

            game = game_service.get_game("test-game")
            stats = game_service.get_reaction_stats(user, game)

            assert stats["best"] == 200
            assert stats["attempts"] == 3
            assert stats["average"] == round((300 + 200 + 250) / 3)
