from datetime import datetime, timedelta

from gaminghub.database.database import db
from gaminghub.services import leaderboard_service
from gaminghub.models.game_result import GameResult
from gaminghub.models.game_session import GameSession


def _play(user, game, score, xp_earned=0, created_at=None):
    session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
    db.session.add(session)
    db.session.commit()
    result = GameResult(
        user_id=user.id, game_id=game.id, game_session_id=session.id,
        result="win", score=score, xp_earned=xp_earned
    )
    if created_at:
        result.created_at = created_at
    db.session.add(result)
    db.session.commit()
    return result


class TestTotalXp:

    def test_reconstructs_lifetime_xp_from_level_and_current_xp(self, make_user):
        # LEVEL_XP is 100. Reaching level 3 cost 100*(1+2)=300, plus 40
        # earned since -- lifetime total should be 340.
        user = make_user(level=3, xp=40)
        assert leaderboard_service._total_xp(user) == 340

    def test_level_one_with_zero_xp_is_zero(self, make_user):
        user = make_user(level=1, xp=0)
        assert leaderboard_service._total_xp(user) == 0


class TestGlobalLeaderboard:

    def test_orders_by_total_xp_descending(self, make_user):
        low = make_user(username="low", level=1, xp=10)
        high = make_user(username="high", level=2, xp=10)

        entries = leaderboard_service.get_global_leaderboard()

        assert [e["user"].username for e in entries] == ["high", "low"]

    def test_ties_share_a_rank_and_the_next_rank_skips(self, make_user):
        # Three users with identical lifetime XP, one strictly lower.
        a = make_user(username="a", level=1, xp=50)
        b = make_user(username="b", level=1, xp=50)
        c = make_user(username="c", level=1, xp=50)
        d = make_user(username="d", level=1, xp=10)

        entries = leaderboard_service.get_global_leaderboard()
        ranks = {e["user"].username: e["rank"] for e in entries}

        assert ranks["a"] == ranks["b"] == ranks["c"] == 1
        assert ranks["d"] == 4  # skips 2 and 3 -- three players share rank 1

    def test_my_global_rank_counts_strictly_higher_players_plus_one(self, make_user):
        make_user(username="ahead1", level=3, xp=0)
        make_user(username="ahead2", level=2, xp=0)
        me = make_user(username="me", level=1, xp=50)

        assert leaderboard_service.get_my_global_rank(me) == 3

    def test_respects_the_limit_parameter(self, make_user):
        for i in range(5):
            make_user(username=f"user{i}", level=1, xp=i)

        entries = leaderboard_service.get_global_leaderboard(limit=2)

        assert len(entries) == 2


class TestPeriodLeaderboard:

    def test_daily_only_counts_results_from_today(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _play(user, game, score=1, xp_earned=50, created_at=datetime.utcnow())
        _play(user, game, score=1, xp_earned=999, created_at=datetime.utcnow() - timedelta(days=2))

        entries = leaderboard_service.get_period_leaderboard("daily")

        assert entries[0]["value"] == 50

    def test_weekly_includes_results_from_the_last_seven_days(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _play(user, game, score=1, xp_earned=30, created_at=datetime.utcnow() - timedelta(days=3))
        _play(user, game, score=1, xp_earned=999, created_at=datetime.utcnow() - timedelta(days=10))

        entries = leaderboard_service.get_period_leaderboard("weekly")

        assert entries[0]["value"] == 30

    def test_my_period_rank_and_value_for_a_player_with_no_results(self, make_user):
        user = make_user()
        rank, value = leaderboard_service.get_my_period_rank(user, "daily")
        assert rank is None
        assert value == 0

    def test_invalid_period_raises(self, make_user):
        import pytest
        with pytest.raises(ValueError):
            leaderboard_service._period_start("monthly")


class TestGameLeaderboard:

    def test_ranks_by_best_score_per_user(self, make_user, make_game):
        game = make_game()
        alice = make_user(username="alice")
        bob = make_user(username="bob")

        _play(alice, game, score=10)
        _play(alice, game, score=90)  # alice's best is 90
        _play(bob, game, score=50)

        entries = leaderboard_service.get_game_leaderboard(game)

        assert entries[0]["user"].username == "alice"
        assert entries[0]["value"] == 90
        assert entries[1]["user"].username == "bob"

    def test_my_game_rank_for_a_player_with_no_results_is_none(self, make_user, make_game):
        user = make_user()
        game = make_game()
        rank, value = leaderboard_service.get_my_game_rank(user, game)
        assert rank is None
        assert value is None


class TestCategoryLeaderboard:

    def test_sums_scores_within_the_category_only(self, make_user, make_game):
        user = make_user()
        brain_game = make_game(slug="brain-game", category="brain-lab")
        classic_game = make_game(slug="classic-game", category="classic-arcade")

        _play(user, brain_game, score=20)
        _play(user, brain_game, score=30)
        _play(user, classic_game, score=999)  # different category, excluded

        entries = leaderboard_service.get_category_leaderboard("brain-lab")

        assert entries[0]["value"] == 50
