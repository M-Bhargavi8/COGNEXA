from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user, login_user

from gaminghub.database.database import limiter
from gaminghub.services import account_service, audit_service

account = Blueprint("account", __name__, url_prefix="/account")


@account.route("/")
@login_required
def settings():
    return render_template(
        "account/settings.html",
        favorite_games=account_service.favorite_game_choices(),
        pending_email=account_service.pending_email(current_user),
        mail_enabled=current_app.config.get("MAIL_BACKEND") != "disabled",
        password_rules={
            "min": account_service.PASSWORD_MIN_LENGTH,
            "max": account_service.PASSWORD_MAX_BYTES,
        },
        bio_max=account_service.BIO_MAX,
        country_max=account_service.COUNTRY_MAX,
    )


@account.route("/profile", methods=["POST"])
@login_required
@limiter.limit("20 per hour")
def update_profile():
    success, message = account_service.update_profile(
        current_user,
        username=request.form.get("username"),
        bio=request.form.get("bio"),
        country=request.form.get("country"),
        favorite_game=request.form.get("favorite_game"),
    )
    flash(message, "success" if success else "danger")
    return redirect(url_for("account.settings") + "#profile")


@account.route("/email", methods=["POST"])
@login_required
@limiter.limit("5 per hour")
def change_email():
    success, message = account_service.request_email_change(
        current_user,
        request.form.get("email"),
        request.form.get("current_password"),
    )
    flash(message, "success" if success else "danger")
    return redirect(url_for("account.settings") + "#email")


@account.route("/password", methods=["POST"])
@login_required
@limiter.limit("5 per 15 minutes")
def change_password():
    user = current_user._get_current_object()

    success, message = account_service.change_password(
        user,
        request.form.get("current_password"),
        request.form.get("new_password"),
        request.form.get("confirm_password"),
    )

    if success:
        # auth_version just changed, which invalidates this browser's
        # session too -- sign it straight back in with the new version.
        login_user(user)

    flash(message, "success" if success else "danger")
    return redirect(url_for("account.settings") + "#password")


@account.route("/verify/resend", methods=["POST"])
@login_required
@limiter.limit("3 per 15 minutes")
def resend_verification():
    if current_user.is_email_verified:
        flash("Your email is already verified.", "info")
    elif account_service.send_verification_email(current_user):
        audit_service.record("verification_resent", actor=current_user, target=current_user)
        flash(f"We sent a new verification link to {current_user.email}.", "success")
    else:
        flash("We couldn't send the email right now. Please try again later.", "danger")

    return redirect(url_for("account.settings") + "#email")
