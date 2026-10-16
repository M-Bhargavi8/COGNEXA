import math

from gaminghub.database.database import db
from gaminghub.models.game_result import GameResult
from gaminghub.models.game_session import GameSession
from gaminghub.services import analytics_service
from gaminghub.utils.radar import build_radar


def _play(user, game, result="win"):
    session = GameSession(user_id=user.id, game_id=game.id, status="completed", state="{}")
    db.session.add(session)
    db.session.commit()
    row = GameResult(
        user_id=user.id, game_id=game.id, game_session_id=session.id,
        result=result, score=0
    )
    db.session.add(row)
    db.session.commit()
    return row


def _profile(scores):
    """A radar profile in SKILLS order; a 0 score means never played."""
    return [
        {"skill": skill, "score": score, "plays": 4 if score else 0}
        for skill, score in zip(analytics_service.SKILLS, scores)
    ]


class TestGetRadarProfile:

    def test_returns_every_skill_even_when_never_played(self, make_user):
        user = make_user()
        profile = analytics_service.get_radar_profile(user)

        assert [e["skill"] for e in profile] == analytics_service.SKILLS
        assert all(e["plays"] == 0 for e in profile)
        assert all(e["score"] == 0 for e in profile)

    def test_unplayed_skills_are_distinguishable_from_a_zero_score(self, make_user, make_game):
        user = make_user()
        _play(user, make_game(slug="memory-matrix"), result="loss")

        by_skill = {e["skill"]: e for e in analytics_service.get_radar_profile(user)}

        # Both score 0, but one was measured and the other never attempted.
        assert by_skill["Memory"]["score"] == 0
        assert by_skill["Memory"]["plays"] == 1
        assert by_skill["Logic"]["plays"] == 0

    def test_score_is_win_rate_for_that_skill(self, make_user, make_game):
        user = make_user()
        game = make_game(slug="memory-matrix")
        _play(user, game, result="win")
        _play(user, game, result="win")
        _play(user, game, result="loss")
        _play(user, game, result="loss")

        by_skill = {e["skill"]: e for e in analytics_service.get_radar_profile(user)}
        assert by_skill["Memory"]["score"] == 50
        assert by_skill["Memory"]["plays"] == 4

    def test_two_games_can_feed_one_skill(self, make_user, make_game):
        user = make_user()
        _play(user, make_game(slug="code-breaker"), result="win")
        _play(user, make_game(slug="logic-grid"), result="loss")

        by_skill = {e["skill"]: e for e in analytics_service.get_radar_profile(user)}
        assert by_skill["Logic"]["plays"] == 2
        assert by_skill["Logic"]["score"] == 50

    def test_without_a_user_it_aggregates_every_player(self, make_user, make_game):
        game = make_game(slug="memory-matrix")
        _play(make_user(username="a", email="a@x.com"), game, result="win")
        _play(make_user(username="b", email="b@x.com"), game, result="loss")

        by_skill = {e["skill"]: e for e in analytics_service.get_radar_profile()}
        assert by_skill["Memory"]["plays"] == 2
        assert by_skill["Memory"]["score"] == 50

    def test_skill_profile_still_omits_unplayed_skills(self, make_user, make_game):
        """The radar variant adds empty axes; the bar-chart one must not."""
        user = make_user()
        _play(user, make_game(slug="memory-matrix"))

        assert [e["skill"] for e in analytics_service.get_skill_profile(user)] == ["Memory"]
        assert len(analytics_service.get_radar_profile(user)) == len(analytics_service.SKILLS)


class TestBuildRadar:

    def test_returns_none_for_a_shape_with_no_area(self):
        assert build_radar(_profile([50, 50])) is None
        assert build_radar([]) is None

    def test_places_vertices_on_a_circle_of_the_right_radius(self):
        data = build_radar(_profile([100] * 7))
        centre, radius = data["centre"], data["radius"]

        for dot in data["dots"]:
            distance = math.hypot(dot["x"] - centre, dot["y"] - centre)
            assert distance == round(radius, 2) or abs(distance - radius) < 0.05

    def test_first_axis_points_straight_up(self):
        data = build_radar(_profile([100] * 7))
        first = data["dots"][0]

        assert first["x"] == data["centre"]
        assert first["y"] < data["centre"]

    def test_an_unplayed_axis_sits_at_the_centre_and_is_flagged(self):
        data = build_radar(_profile([80, 0, 70, 60, 90, 50, 40]))

        assert data["axes"][1]["empty"] is True
        assert data["dots"][1]["x"] == data["centre"]
        assert data["dots"][1]["y"] == data["centre"]
        assert data["axes"][0]["empty"] is False

    def test_needs_three_measured_axes_before_drawing_a_polygon(self):
        assert build_radar(_profile([80, 90, 0, 0, 0, 0, 0]))["has_data"] is False
        assert build_radar(_profile([80, 90, 70, 0, 0, 0, 0]))["has_data"] is True

    def test_reports_how_many_axes_were_measured(self):
        assert build_radar(_profile([80, 90, 0, 0, 0, 0, 0]))["measured"] == 2
        assert build_radar(_profile([1] * 7))["measured"] == 7

    def test_scores_are_clamped_into_the_chart(self):
        data = build_radar(_profile([500, 100, 100, 100, 100, 100, 100]))
        centre, radius = data["centre"], data["radius"]

        assert math.hypot(
            data["dots"][0]["x"] - centre, data["dots"][0]["y"] - centre
        ) <= radius + 0.05

    def test_labels_are_anchored_away_from_the_chart(self):
        data = build_radar(_profile([100] * 7))
        centre = data["centre"]

        for axis in data["axes"]:
            if axis["label_x"] > centre + 12:
                assert axis["anchor"] == "start"
            elif axis["label_x"] < centre - 12:
                assert axis["anchor"] == "end"
            else:
                assert axis["anchor"] == "middle"

    def test_long_skill_names_get_a_short_drawn_label(self):
        data = build_radar(_profile([100] * 7))
        by_label = {a["label"]: a for a in data["axes"]}

        assert by_label["Pattern Recognition"]["short"] == "Patterns"
        # The full name survives for the accessible description.
        assert by_label["Pattern Recognition"]["label"] == "Pattern Recognition"
        assert by_label["Memory"]["short"] == "Memory"

    def test_comparison_ring_is_only_added_when_it_has_enough_data(self):
        full = _profile([70] * 7)

        assert "compare_points" not in build_radar(full)
        assert build_radar(full, compare=_profile([60] * 7))["compare_has_data"] is True
        assert build_radar(full, compare=_profile([60, 60, 0, 0, 0, 0, 0]))["compare_has_data"] is False

    def test_a_mismatched_comparison_is_ignored(self):
        """Overlaying a profile with different axes would draw a lie."""
        data = build_radar(_profile([70] * 7), compare=_profile([60] * 7)[:5])
        assert "compare_points" not in data

    def test_view_box_is_wider_than_the_geometry_to_fit_labels(self):
        data = build_radar(_profile([100] * 7))
        min_x, _, width, _ = (float(v) for v in data["view_box"].split())

        assert min_x < 0
        assert width > data["size"]
