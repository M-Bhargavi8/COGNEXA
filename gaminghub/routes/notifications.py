from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required, current_user

from gaminghub.services import notification_service

notifications = Blueprint("notifications", __name__)


@notifications.route("/notifications")
@login_required
def notifications_home():
    return render_template(
        "notifications.html",
        notifications=notification_service.get_recent(current_user, limit=50)
    )


@notifications.route("/notifications/open/<int:notification_id>")
@login_required
def open_notification(notification_id):
    """Marks a notification read, then sends the user to whatever it's about."""

    notification = notification_service.mark_read(current_user, notification_id)

    if notification and notification.link:
        return redirect(notification.link)

    return redirect(url_for("notifications.notifications_home"))


@notifications.route("/notifications/read/<int:notification_id>", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification_service.mark_read(current_user, notification_id)
    return redirect(url_for("notifications.notifications_home"))


@notifications.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_read():
    notification_service.mark_all_read(current_user)
    return redirect(url_for("notifications.notifications_home"))
