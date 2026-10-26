import logging

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user

from gaminghub.database.database import db, limiter
from gaminghub.models.account_token import PURPOSE_PASSWORD_RESET
from gaminghub.models.user import User
from gaminghub.services import account_service, audit_service
from gaminghub.utils.security import is_safe_redirect_target

auth = Blueprint("auth", __name__)

logger = logging.getLogger(__name__)

# Kept for anything importing it from here; the rule now lives in
# account_service with the rest of the validation.
EMAIL_RE = account_service.EMAIL_RE

RESET_SESSION_KEY = "password_reset_token"


@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard_home"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = account_service.normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error = (
            account_service.validate_username(username)
            or account_service.validate_email(email)
            or account_service.validate_password(password)
        )

        if not error and password != confirm_password:
            error = "Passwords do not match."

        if not error and account_service.username_taken(username):
            error = "Username already exists."

        if not error and account_service.email_taken(email):
            error = "Email already registered."

        if error:
            flash(error, "danger")
            return redirect(url_for("auth.register"))

        new_user = User(
            username=username,
            email=email,
            password=account_service.hash_password(password)
        )

        db.session.add(new_user)
        db.session.commit()

        account_service.send_verification_email(new_user)

        flash("Registration successful! We sent a verification link to your email. Please login.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():

    next_url = request.args.get("next") or request.form.get("next")
    if not is_safe_redirect_target(next_url):
        next_url = None

    if current_user.is_authenticated:
        return redirect(next_url or url_for("dashboard.dashboard_home"))

    if request.method == "POST":

        user, error = account_service.authenticate(
            request.form.get("email"),
            request.form.get("password")
        )

        if user:
            login_user(user, remember=bool(request.form.get("remember")))
            account_service.record_login(user)

            flash("Login Successful!", "success")

            return redirect(next_url or url_for("dashboard.dashboard_home"))

        logger.info("Failed login attempt from %s", request.remote_addr)
        flash(error, "danger")

    return render_template(
        "login.html",
        next_url=next_url,
        verification_required=current_app.config.get("EMAIL_VERIFICATION_REQUIRED")
    )


@auth.route("/logout", methods=["POST"])
def logout():

    logout_user()

    flash("Logged out successfully.", "success")

    return redirect(url_for("main.home"))


# ------------------------------------------------------- password reset

@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def forgot_password():

    if request.method == "POST":
        email = account_service.normalize_email(request.form.get("email"))

        if account_service.validate_email(email):
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("auth.forgot_password"))

        account_service.request_password_reset(email)

        # Same answer whether or not the address is registered.
        flash("If an account exists for that email, we've sent a link to reset the password.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth.route("/reset-password/<token>")
@limiter.limit("20 per 15 minutes")
def reset_password_landing(token):
    """The emailed link lands here. The token moves into the (signed)
    session and the browser is redirected to a URL without it, so it
    doesn't linger in history, referrers or later access-log lines."""

    if not account_service.get_valid_token(token, PURPOSE_PASSWORD_RESET):
        flash("That reset link is invalid or has expired. Request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    session[RESET_SESSION_KEY] = token
    return redirect(url_for("auth.reset_password"))


@auth.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("10 per 15 minutes", methods=["POST"])
def reset_password():

    token = session.get(RESET_SESSION_KEY)

    if not token or not account_service.get_valid_token(token, PURPOSE_PASSWORD_RESET):
        session.pop(RESET_SESSION_KEY, None)
        flash("That reset link is invalid or has expired. Request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        success, message = account_service.reset_password(
            token,
            request.form.get("password", ""),
            request.form.get("confirm_password", "")
        )

        if success:
            session.pop(RESET_SESSION_KEY, None)
            logout_user()
            flash(message, "success")
            return redirect(url_for("auth.login"))

        flash(message, "danger")

    return render_template("auth/reset_password.html")


# --------------------------------------------------- email verification

@auth.route("/verify-email/<token>")
@limiter.limit("20 per 15 minutes")
def verify_email(token):

    success, message = account_service.verify_email(token)
    flash(message, "success" if success else "danger")

    if current_user.is_authenticated:
        return redirect(url_for("account.settings"))

    return redirect(url_for("auth.login"))


@auth.route("/verify-email/resend", methods=["GET", "POST"])
@limiter.limit("3 per 15 minutes", methods=["POST"])
def resend_verification():
    """For signed-out visitors -- mainly accounts that can't log in yet
    because EMAIL_VERIFICATION_REQUIRED is on. Signed-in users resend
    from their account page instead."""

    if current_user.is_authenticated:
        return redirect(url_for("account.settings"))

    if request.method == "POST":
        user = account_service.find_user_by_email(request.form.get("email"))

        if user and user.is_active and not user.is_email_verified:
            account_service.send_verification_email(user)
            audit_service.record("verification_resent", actor=user, target=user)

        flash("If that account needs verifying, we've sent a new link.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/resend_verification.html")
