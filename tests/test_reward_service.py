from datetime import datetime, timedelta, date

from gaminghub.services import reward_service
from gaminghub.models.notification import Notification


class TestAward:

    def test_grants_xp_and_coins(self, make_user):
        user = make_user()
        reward_service.award(user, xp=30, coins=15)
        assert user.xp == 30
        assert user.coins == 115  # User.coins defaults to 100

    def test_applies_a_single_level_up(self, make_user):
        user = make_user()  # level 1, xp 0; LEVEL_XP is 100
        reward_service.award(user, xp=150)
        assert user.level == 2
        assert user.xp == 50  # 150 - (1 * 100)

    def test_applies_multiple_level_ups_in_one_grant(self, make_user):
        user = make_user()
        reward_service.award(user, xp=100 + 200 + 5)  # enough for level 1->2->3
        assert user.level == 3
        assert user.xp == 5

    def test_outcome_win_increments_games_played_and_wins(self, make_user):
        user = make_user()
        reward_service.award(user, outcome="win")
        assert user.games_played == 1
        assert user.wins == 1
        assert user.losses == 0

    def test_outcome_loss_increments_games_played_and_losses(self, make_user):
        user = make_user()
        reward_service.award(user, outcome="loss")
        assert user.games_played == 1
        assert user.losses == 1
        assert user.wins == 0

    def test_outcome_draw_increments_games_played_only(self, make_user):
        user = make_user()
        reward_service.award(user, outcome="draw")
        assert user.games_played == 1
        assert user.wins == 0
        assert user.losses == 0

    def test_outcome_none_leaves_win_loss_counters_untouched(self, make_user):
        user = make_user()
        reward_service.award(user, coins=10)  # e.g. the daily claim path
        assert user.games_played == 0
        assert user.wins == 0
        assert user.losses == 0

    def test_doubles_xp_when_booster_is_active(self, make_user):
        user = make_user(xp_booster_expires_at=datetime.utcnow() + timedelta(hours=1))
        reward_service.award(user, xp=20)
        assert user.xp == 40

    def test_does_not_double_xp_when_booster_expired(self, make_user):
        user = make_user(xp_booster_expires_at=datetime.utcnow() - timedelta(hours=1))
        reward_service.award(user, xp=20)
        assert user.xp == 20

    def test_updates_high_score_when_xp_exceeds_it(self, make_user):
        user = make_user()
        assert user.high_score == 0
        reward_service.award(user, xp=25)
        assert user.high_score == 25
        reward_service.award(user, xp=10)  # smaller grant afterward shouldn't lower it
        assert user.high_score == 25

    def test_creates_a_level_up_notification(self, make_user, db):
        user = make_user()
        reward_service.award(user, xp=150)
        notifications = Notification.query.filter_by(user_id=user.id, type="level_up").all()
        assert len(notifications) == 1
        assert "Level 2" in notifications[0].title

    def test_does_not_create_a_level_up_notification_without_one(self, make_user, db):
        user = make_user()
        reward_service.award(user, xp=10)
        assert Notification.query.filter_by(user_id=user.id, type="level_up").count() == 0

    def test_unlocks_and_notifies_achievements(self, make_user, make_achievement, db):
        make_achievement("First Game", title="First Game", coin_reward=20)
        make_achievement("First Win", title="First Victory", coin_reward=50, xp_reward=50)

        user = make_user()
        unlocked = reward_service.award(user, outcome="win")

        unlocked_names = {a.name for a in unlocked}
        assert unlocked_names == {"First Game", "First Win"}

        achievement_notifs = Notification.query.filter_by(user_id=user.id, type="achievement").all()
        assert len(achievement_notifs) == 2

    def test_no_achievement_row_means_silent_no_op(self, make_user):
        """check_achievements looks achievements up by name -- if the catalog
        row doesn't exist (e.g. an empty test DB), unlock() just returns
        None rather than erroring."""
        user = make_user()
        unlocked = reward_service.award(user, outcome="win")
        assert unlocked == []


class TestClaimDailyReward:

    def test_first_claim_succeeds_with_streak_one(self, make_user):
        user = make_user(coins=0)
        success, message, reward = reward_service.claim_daily_reward(user)

        assert success is True
        assert reward == 20  # streak 1 * 20
        assert user.daily_streak == 1
        assert user.coins == 20
        assert user.last_claim == date.today()

    def test_same_day_claim_is_rejected(self, make_user):
        user = make_user(last_claim=date.today(), daily_streak=1)
        success, message, reward = reward_service.claim_daily_reward(user)

        assert success is False
        assert reward == 0
        assert "already claimed" in message.lower()
        assert user.daily_streak == 1  # untouched

    def test_consecutive_day_increments_streak(self, make_user):
        user = make_user(last_claim=date.today() - timedelta(days=1), daily_streak=3, coins=0)
        success, message, reward = reward_service.claim_daily_reward(user)

        assert success is True
        assert user.daily_streak == 4
        assert reward == 80  # streak 4 * 20

    def test_gap_in_days_resets_streak_to_one(self, make_user):
        user = make_user(last_claim=date.today() - timedelta(days=5), daily_streak=10, coins=0)
        success, message, reward = reward_service.claim_daily_reward(user)

        assert success is True
        assert user.daily_streak == 1
        assert reward == 20


class TestXpProgress:

    def test_returns_xp_needed_and_percent(self, make_user):
        user = make_user()
        user.level = 2
        user.xp = 50  # needs level(2) * LEVEL_XP(100) = 200
        xp, needed, percent = reward_service.xp_progress(user)

        assert xp == 50
        assert needed == 200
        assert percent == 25
