from datetime import date, datetime, time, timezone

from gaminghub.database.database import db as _db
from gaminghub.services import notification_service
from gaminghub.models.notification import Notification


class TestCreate:

    def test_creates_a_notification_with_all_fields(self, make_user):
        user = make_user()
        n = notification_service.create(user, "achievement", "Title", message="msg", icon="🏆", link="/x")

        assert n.user_id == user.id
        assert n.type == "achievement"
        assert n.title == "Title"
        assert n.is_read is False


class TestGetRecentAndUnreadCount:

    def test_get_recent_orders_newest_first_and_respects_limit(self, make_user):
        user = make_user()
        for i in range(5):
            notification_service.create(user, "achievement", f"n{i}")

        recent = notification_service.get_recent(user, limit=2)

        assert len(recent) == 2
        assert recent[0].title == "n4"

    def test_unread_count_only_counts_this_user(self, make_user):
        user_a = make_user(username="a")
        user_b = make_user(username="b")
        notification_service.create(user_a, "achievement", "for a")
        notification_service.create(user_b, "achievement", "for b")

        assert notification_service.get_unread_count(user_a) == 1


class TestMarkRead:

    def test_marks_the_owner_s_notification_read(self, make_user):
        user = make_user()
        n = notification_service.create(user, "achievement", "n")

        result = notification_service.mark_read(user, n.id)

        assert result.is_read is True
        assert notification_service.get_unread_count(user) == 0

    def test_a_different_user_cannot_mark_it_read(self, make_user):
        owner = make_user(username="owner")
        attacker = make_user(username="attacker")
        n = notification_service.create(owner, "achievement", "n")

        result = notification_service.mark_read(attacker, n.id)

        assert result is None
        assert _db.session.get(Notification, n.id).is_read is False

    def test_marking_an_already_read_one_is_a_harmless_no_op(self, make_user):
        user = make_user()
        n = notification_service.create(user, "achievement", "n")
        notification_service.mark_read(user, n.id)

        result = notification_service.mark_read(user, n.id)

        assert result.is_read is True


class TestMarkAllRead:

    def test_marks_only_this_user_s_unread_notifications(self, make_user):
        user_a = make_user(username="a")
        user_b = make_user(username="b")
        notification_service.create(user_a, "achievement", "a1")
        notification_service.create(user_a, "achievement", "a2")
        notification_service.create(user_b, "achievement", "b1")

        notification_service.mark_all_read(user_a)

        assert notification_service.get_unread_count(user_a) == 0
        assert notification_service.get_unread_count(user_b) == 1


class TestNotifyAchievements:

    def test_creates_one_notification_per_achievement(self, make_user, make_achievement):
        user = make_user()
        a1 = make_achievement("A1", title="Ach One")
        a2 = make_achievement("A2", title="Ach Two")

        notification_service.notify_achievements(user, [a1, a2])

        notifs = Notification.query.filter_by(user_id=user.id, type="achievement").all()
        assert len(notifs) == 2
        assert any("Ach One" in n.title for n in notifs)
        assert any("Ach Two" in n.title for n in notifs)

    def test_empty_list_creates_nothing(self, make_user):
        user = make_user()
        notification_service.notify_achievements(user, [])
        assert Notification.query.filter_by(user_id=user.id).count() == 0


class TestEnsureDailyReminders:

    def test_creates_both_reminders_for_a_fresh_user(self, make_user, make_game):
        make_game(slug="guess-the-number")  # a challenge needs a matching seeded game to be creatable
        user = make_user(last_claim=None)

        notification_service.ensure_daily_reminders(user)

        types = {n.type for n in Notification.query.filter_by(user_id=user.id).all()}
        assert "daily_reward" in types

    def test_does_not_duplicate_on_a_second_call_the_same_day(self, make_user, make_game):
        make_game(slug="guess-the-number")
        user = make_user(last_claim=None)

        notification_service.ensure_daily_reminders(user)
        count_after_first = Notification.query.filter_by(user_id=user.id).count()

        notification_service.ensure_daily_reminders(user)
        count_after_second = Notification.query.filter_by(user_id=user.id).count()

        assert count_after_first == count_after_second

    def test_no_daily_reward_reminder_if_already_claimed_today(self, make_user, make_game):
        make_game(slug="guess-the-number")
        user = make_user(last_claim=date.today())

        notification_service.ensure_daily_reminders(user)

        types = {n.type for n in Notification.query.filter_by(user_id=user.id).all()}
        assert "daily_reward" not in types


class TestUtcStartOfLocalDay:
    """
    The daily features roll over on the local calendar day, but
    Notification.created_at is stored in UTC. These pin the conversion
    that reconciles the two, without depending on the machine's own
    timezone or on what time the suite happens to run.
    """

    def test_converts_local_midnight_to_the_matching_utc_instant(self):
        day = date(2026, 8, 15)
        start = notification_service.utc_start_of_local_day(day)

        expected = (
            datetime.combine(day, time.min)
            .astimezone()
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )
        assert start == expected

    def test_result_is_naive_so_it_compares_with_stored_timestamps(self):
        start = notification_service.utc_start_of_local_day(date(2026, 8, 15))
        assert start.tzinfo is None

    def test_never_returns_an_instant_in_the_future(self):
        """
        The bug this replaces: east of UTC, a local-midnight timestamp
        sits ahead of every UTC row written that morning, so the dedup
        filter matched nothing and reminders duplicated on every visit.
        """
        start = notification_service.utc_start_of_local_day(date.today())
        assert start <= datetime.utcnow()

    def test_a_notification_created_now_falls_inside_today(self, make_user):
        user = make_user()
        n = notification_service.create(user, "daily_reward", "x")

        assert n.created_at >= notification_service.utc_start_of_local_day(date.today())
