from datetime import date, datetime, time, timezone

from sqlalchemy import func

from gaminghub.database.database import db
from gaminghub.models.notification import Notification


# Every notification `type` the app actually creates (see the create()
# call sites in reward_service, game_service and ensure_daily_reminders
# below) grouped into the filter categories the notification center
# shows. Kept here, next to create(), so a new type can't be added
# without a human deciding which tab it belongs on.
CATEGORIES = {
    "achievements": ["achievement"],
    "rewards": ["daily_reward"],
    "game_activity": ["level_up", "personal_best", "challenge"],
    "system": ["daily_challenge"],
}

CATEGORY_LABELS = {
    "all": "All",
    "achievements": "Achievements",
    "rewards": "Rewards",
    "game_activity": "Game Activity",
    "system": "System",
}


def create(user, type_, title, *, message=None, icon="bell", link=None):
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


def get_recent(user, limit=8, category=None):
    query = Notification.query.filter_by(user_id=user.id)

    if category and category != "all":
        query = query.filter(Notification.type.in_(CATEGORIES.get(category, [])))

    return query.order_by(Notification.created_at.desc()).limit(limit).all()


def has_any(user):
    return db.session.query(
        Notification.query.filter_by(user_id=user.id).exists()
    ).scalar()


def get_unread_count(user):
    return Notification.query.filter_by(user_id=user.id, is_read=False).count()


def get_unread_counts_by_category(user):
    """{'all': N, 'achievements': N, 'rewards': N, ...} -- real unread
    totals per tab, computed with one grouped query rather than one
    query per category."""

    rows = db.session.query(Notification.type, func.count()) \
        .filter_by(user_id=user.id, is_read=False) \
        .group_by(Notification.type).all()

    type_counts = dict(rows)

    counts = {"all": sum(type_counts.values())}
    for category, types in CATEGORIES.items():
        counts[category] = sum(type_counts.get(t, 0) for t in types)

    return counts


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
            message=achievement.description, icon="achievement", link="/profile"
        )


def utc_start_of_local_day(day):
    """
    The UTC instant that local midnight on `day` corresponds to.

    Notification.created_at is stored in UTC (datetime.utcnow), but the
    daily features -- the reward claim, the daily challenge, and these
    reminders -- all roll over on the *local* calendar day via
    date.today(). Comparing a local-midnight timestamp directly against
    UTC rows silently matches nothing for however long the two dates
    disagree: on a UTC+5:30 host that is every day between midnight and
    05:30, during which the dedup below let a duplicate pair of
    reminders through on every single dashboard visit.

    Converting through astimezone() rather than subtracting
    utcnow() - now() keeps this correct across DST boundaries.
    """
    local_midnight = datetime.combine(day, time.min).astimezone()
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


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
    today_start = utc_start_of_local_day(today)

    if user.last_claim != today and not _already_reminded_today(user, "daily_reward", today_start):
        create(
            user, "daily_reward", "Daily Reward Available",
            message="Claim today's login reward.", icon="reward", link="/daily"
        )

    if not challenge_service.has_completed_today(user) and not _already_reminded_today(user, "daily_challenge", today_start):
        create(
            user, "daily_challenge", "Daily Challenge Available",
            message="A new challenge is ready on your dashboard.", icon="flame", link="/dashboard"
        )
