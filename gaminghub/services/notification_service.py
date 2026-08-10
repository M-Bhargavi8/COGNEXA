from datetime import date, datetime

from gaminghub.database.database import db
from gaminghub.models.notification import Notification


def create(user, type_, title, *, message=None, icon="🔔", link=None):
    notification = Notification(
        user_id=user.id,
        type=type_,
        title=title,
        message=message,
        icon=icon,
        link=link
    )

    db.session.add(notification)
    db.session.commit()

    return notification


def get_recent(user, limit=8):
    return Notification.query.filter_by(user_id=user.id) \
        .order_by(Notification.created_at.desc()).limit(limit).all()


def get_unread_count(user):
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def mark_read(user, notification_id):
    notification = Notification.query.filter_by(id=notification_id, user_id=user.id).first()

    if notification and not notification.is_read:
        notification.is_read = True
        db.session.commit()

    return notification


def mark_all_read(user):
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()


def notify_achievements(user, achievements):
    """Shared by reward_service.award() and game_service.complete_session(),
    the two places achievement unlocks can come from."""

    for achievement in achievements:
        create(
            user, "achievement", f"Achievement Unlocked: {achievement.title}",
            message=achievement.description, icon=achievement.badge or "🏆", link="/profile"
        )


def _already_reminded_today(user, type_, today_start):
    return Notification.query.filter(
        Notification.user_id == user.id,
        Notification.type == type_,
        Notification.created_at >= today_start
    ).first() is not None


def ensure_daily_reminders(user):
    """
    Creates "available" reminder notifications at most once per calendar
    day each, the first time the user is seen that day (called from the
    dashboard route). There's no background scheduler in this app, so
    these are generated lazily on visit rather than pushed proactively.
    """

    # imported here, not at module load time: challenge_service imports
    # reward_service, which imports this module -- a top-level import
    # here would be circular.
    from gaminghub.services import challenge_service

    today = date.today()
    today_start = datetime(today.year, today.month, today.day)

    if user.last_claim != today and not _already_reminded_today(user, "daily_reward", today_start):
        create(
            user, "daily_reward", "Daily Reward Available",
            message="Claim today's login reward.", icon="🎁", link="/daily"
        )

    if not challenge_service.has_completed_today(user) and not _already_reminded_today(user, "daily_challenge", today_start):
        create(
            user, "daily_challenge", "Daily Challenge Available",
            message="A new challenge is ready on your dashboard.", icon="🔥", link="/dashboard"
        )
