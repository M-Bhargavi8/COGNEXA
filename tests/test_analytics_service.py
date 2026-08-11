from gaminghub.database.database import db
from gaminghub.services import analytics_service
from gaminghub.models.game_result import GameResult
from gaminghub.models.game_session import GameSession


def _play(user, game, **kwargs):
    session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
    db.session.add(session)
    db.session.commit()
    defaults = {"result": "win", "score": 0}
    defaults.update(kwargs)
    result = GameResult(user_id=user.id, game_id=game.id, game_session_id=session.id, **defaults)
    db.session.add(result)
    db.session.commit()
    return result


class TestGetOverview:

    def test_pulls_level_xp_coins_directly_from_the_user_row(self, make_user):
        user = make_user(level=3, xp=40, coins=250, daily_streak=5)
        overview = analytics_service.get_overview(user)

        assert overview["level"] == 3
        assert overview["xp"] == 40
        assert overview["coins"] == 250
        assert overview["streak"] == 5

    def test_win_rate_is_none_with_no_games_played(self, make_user):
        user = make_user(games_played=0)
        assert analytics_service.get_overview(user)["win_rate"] is None

    def test_win_rate_is_computed_as_a_percentage(self, make_user):
        user = make_user(games_played=4, wins=3)
        assert analytics_service.get_overview(user)["win_rate"] == 75

    def test_best_score_reflects_the_highest_game_result(self, make_user, make_game):
        user = make_user()
        game = make_game()
        _play(user, game, score=10)
        _play(user, game, score=90)
        _play(user, game, score=40)

        assert analytics_service.get_overview(user)["best_score"] == 90


class TestGetPerGameBreakdown:
    """Wrapped in a request context throughout, not just where a slug
    happens to be recognized -- get_play_url()'s early-return for an
    unrecognized slug is a coincidence to not rely on, not a guarantee."""

    def test_groups_by_game_and_computes_win_rate(self, app, make_user, make_game):
        user = make_user()
        game = make_game(name="Test Game", slug="test-game")
        _play(user, game, result="win", score=10)
        _play(user, game, result="loss", score=5)

        with app.test_request_context():
            breakdown = analytics_service.get_per_game_breakdown(user)

        assert len(breakdown) == 1
        row = breakdown[0]
        assert row["name"] == "Test Game"
        assert row["plays"] == 2
        assert row["win_rate"] == 50
        assert row["best_score"] == 10

    def test_only_includes_games_the_user_has_actually_played(self, app, make_user, make_game):
        user = make_user()
        make_game(slug="unplayed-game")
        with app.test_request_context():
            assert analytics_service.get_per_game_breakdown(user) == []


class TestGetSkillProfile:

    def test_maps_known_game_slugs_to_skills(self, make_user, make_game):
        user = make_user()
        game = make_game(slug="reflex-lab", category="brain-lab")
        _play(user, game, result="win")
        _play(user, game, result="win")
        _play(user, game, result="loss")

        profile = analytics_service.get_skill_profile(user)

        reaction_skill = next((p for p in profile if p["skill"] == "Reaction"), None)
        assert reaction_skill is not None
        assert reaction_skill["plays"] == 3
        assert reaction_skill["score"] == round(100 * 2 / 3)

    def test_a_skill_never_played_is_omitted_not_shown_as_zero(self, make_user, make_game):
        user = make_user()
        make_game(slug="reflex-lab", category="brain-lab")  # never played

        profile = analytics_service.get_skill_profile(user)

        assert all(p["skill"] != "Reaction" for p in profile)


class TestGetRecommendations:
    """get_recommendations calls game_service.get_play_url(), which calls
    url_for() -- and only actually reaches url_for() for a slug that's a
    real, recognized game (an unrecognized slug short-circuits to None
    first). Real slugs need an active request context here."""

    def test_recommends_unplayed_brain_lab_games_first(self, app, make_user, make_game):
        user = make_user()
        make_game(slug="memory-matrix", category="brain-lab", name="Memory Matrix")

        with app.test_request_context():
            recs = analytics_service.get_recommendations(user)

        assert len(recs) == 1
        assert recs[0]["game"].slug == "memory-matrix"
        assert "haven't tried" in recs[0]["reason"]

    def test_respects_the_limit(self, app, make_user, make_game):
        user = make_user()
        for slug in ["memory-matrix", "reflex-lab", "focus-shift", "sequence-breaker", "code-breaker"]:
            make_game(slug=slug, category="brain-lab", name=slug)

        with app.test_request_context():
            recs = analytics_service.get_recommendations(user, limit=2)

        assert len(recs) == 2
