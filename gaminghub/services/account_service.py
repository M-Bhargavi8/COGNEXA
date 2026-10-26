"""
Account self-service: credentials, email verification, password reset
and profile edits. Routes stay thin and call into here, the same way
game routes call game_service.

Every function that can fail returns (success, message) so routes can
flash the message directly.
"""

import hashlib
import re
import secrets
from datetime import datetime, timedelta

from flask import current_app, url_for
from sqlalchemy import func, update

from gaminghub.database.database import db, bcrypt
from gaminghub.models.account_token import AccountToken, PURPOSE_EMAIL_VERIFY, PURPOSE_PASSWORD_RESET
from gaminghub.models.api_token import ApiToken
from gaminghub.models.game import Game
from gaminghub.models.user import User
from gaminghub.services import audit_service
from gaminghub.services.email_service import send_email


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")

PASSWORD_MIN_LENGTH = 8
# bcrypt only reads the first 72 bytes, and bcrypt>=5 raises instead of
# silently truncating -- so anything longer has to be rejected up front.
PASSWORD_MAX_BYTES = 72

BIO_MAX = 300
COUNTRY_MAX = 50

# A reset request for an account that already got a link this recently
# is answered with the same generic message but sends nothing, so the
# form can't be used to flood someone's inbox.
RESET_EMAIL_COOLDOWN = timedelta(minutes=2)

INVALID_CREDENTIALS = "Invalid Email or Password"

# Checked against when the email doesn't match any account, so a failed
# login takes as long as a wrong password and doesn't reveal which
# addresses are registered.
_DUMMY_HASH = None


# ----------------------------------------------------------- validation

def normalize_email(email):
    return (email or "").strip().lower()


def validate_username(username):
    if not USERNAME_RE.match(username or ""):
        return "Username must be 3-30 characters: letters, numbers, dots, dashes or underscores."
    return None


def validate_email(email):
    if not EMAIL_RE.match(email or "") or len(email) > 120:
        return "Enter a valid email address."
    return None


def validate_password(password):
    password = password or ""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Password must be at least {PASSWORD_MIN_LENGTH} characters."
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return f"Password must be at most {PASSWORD_MAX_BYTES} bytes long."
    if not password.strip():
        return "Password can't be only spaces."
    return None


def username_taken(username, exclude_user=None):
    query = User.query.filter(func.lower(User.username) == username.lower())
    if exclude_user is not None:
        query = query.filter(User.id != exclude_user.id)
    return db.session.query(query.exists()).scalar()


def email_taken(email, exclude_user=None):
    query = User.query.filter(func.lower(User.email) == email.lower())
    if exclude_user is not None:
        query = query.filter(User.id != exclude_user.id)
    return db.session.query(query.exists()).scalar()


# ------------------------------------------------------------ passwords

def hash_password(password):
    return bcrypt.generate_password_hash(password).decode("utf-8")


def check_password(user, password):
    """Constant-shape credential check: never raises on over-long input,
    and spends a bcrypt round even when there's no such user."""

    global _DUMMY_HASH

    password = password or ""
    too_long = len(password.encode("utf-8")) > PASSWORD_MAX_BYTES
    candidate = password.encode("utf-8")[:PASSWORD_MAX_BYTES].decode("utf-8", "ignore")

    if user is None:
        if _DUMMY_HASH is None:
            _DUMMY_HASH = hash_password(secrets.token_hex(16))
        bcrypt.check_password_hash(_DUMMY_HASH, candidate)
        return False

    try:
        matches = bcrypt.check_password_hash(user.password, candidate)
    except ValueError:
        return False

    # A password that had to be truncated to be checked can never have
    # been set through this app (validate_password rejects it), so it's
    # never a match even if its first 72 bytes are.
    return matches and not too_long


def find_user_by_email(email):
    email = normalize_email(email)
    if not email:
        return None
    return User.query.filter(func.lower(User.email) == email).first()


def authenticate(email, password):
    """Returns (user, error). error is None on success."""

    user = find_user_by_email(email)

    if not check_password(user, password):
        return None, INVALID_CREDENTIALS

    if not user.is_active:
        return None, "This account is not active. Contact support if you think this is a mistake."

    if current_app.config.get("EMAIL_VERIFICATION_REQUIRED") and not user.is_email_verified:
        return None, "Please verify your email address before logging in."

    return user, None


def record_login(user):
    user.last_login = datetime.utcnow()
    db.session.commit()


def _invalidate_sessions(user):
    """Signs the user out everywhere: bumps auth_version (session and
    remember-me cookies) and revokes every API token."""

    user.auth_version = (user.auth_version or 0) + 1
    ApiToken.query.filter_by(user_id=user.id).delete()


def change_password(user, current_password, new_password, confirm_password):
    if not check_password(user, current_password):
        return False, "Your current password is incorrect."

    error = validate_password(new_password)
    if error:
        return False, error

    if new_password != confirm_password:
        return False, "New passwords do not match."

    if check_password(user, new_password):
        return False, "Choose a password different from your current one."

    _set_password(user, new_password)
    audit_service.record("password_changed", actor=user, target=user, commit=False)
    db.session.commit()

    send_email(
        user.email,
        "Your COGNEXA password was changed",
        f"Hi {user.username},\n\n"
        "The password for your COGNEXA account was just changed, and every "
        "other signed-in device and API token was signed out.\n\n"
        "If this wasn't you, reset your password straight away:\n"
        f"{external_url('auth.forgot_password')}\n"
    )

    return True, "Password updated. Other devices have been signed out."


def _set_password(user, new_password):
    user.password = hash_password(new_password)
    user.password_changed_at = datetime.utcnow()
    _invalidate_sessions(user)


# --------------------------------------------------------------- tokens

def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode()).hexdigest()


def external_url(endpoint, **values):
    """An absolute link built from the configured APP_BASE_URL, never
    from the request's Host header (which the client controls)."""

    return current_app.config["APP_BASE_URL"].rstrip("/") + url_for(endpoint, **values)


def issue_token(user, purpose, *, email=None):
    """Creates a token and returns the raw value (only its hash is
    stored). Any earlier unused token for the same purpose is retired,
    so only the newest link works."""

    now = datetime.utcnow()

    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == purpose,
        AccountToken.used_at.is_(None)
    ).update({"used_at": now}, synchronize_session=False)

    max_age = current_app.config[
        "PASSWORD_RESET_TOKEN_MAX_AGE" if purpose == PURPOSE_PASSWORD_RESET else "EMAIL_VERIFICATION_TOKEN_MAX_AGE"
    ]

    raw_token = secrets.token_urlsafe(32)

    db.session.add(AccountToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=_hash_token(raw_token),
        email=email,
        created_at=now,
        expires_at=now + timedelta(seconds=max_age),
    ))
    db.session.commit()

    return raw_token


def get_valid_token(raw_token, purpose):
    if not raw_token or len(raw_token) > 200:
        return None

    token = AccountToken.query.filter_by(token_hash=_hash_token(raw_token), purpose=purpose).first()

    if not token or token.used_at is not None or token.expires_at <= datetime.utcnow():
        return None

    if not token.user or not token.user.is_active:
        return None

    return token


def _consume(token):
    """Marks the token used. The conditional UPDATE makes this the single
    point where two concurrent redemptions are decided: only one of them
    can flip used_at from NULL."""

    result = db.session.execute(
        update(AccountToken)
        .where(AccountToken.id == token.id, AccountToken.used_at.is_(None))
        .values(used_at=datetime.utcnow())
    )
    return result.rowcount == 1


# --------------------------------------------------- email verification

def send_verification_email(user, email=None):
    """email defaults to the user's current address; pass a different one
    to verify a pending email change. Returns True if a message was sent."""

    email = email or user.email
    raw_token = issue_token(user, PURPOSE_EMAIL_VERIFY, email=email)
    link = external_url("auth.verify_email", token=raw_token)
    hours = current_app.config["EMAIL_VERIFICATION_TOKEN_MAX_AGE"] // 3600

    return send_email(
        email,
        "Verify your COGNEXA email address",
        f"Hi {user.username},\n\n"
        f"Confirm this email address for your COGNEXA account:\n{link}\n\n"
        f"The link works once and expires in {hours} hours. "
        "If you didn't ask for this, you can ignore this message.\n"
    )


def verify_email(raw_token):
    token = get_valid_token(raw_token, PURPOSE_EMAIL_VERIFY)

    if not token:
        return False, "That verification link is invalid or has expired. Request a new one from your account page."

    user = token.user
    new_email = token.email or user.email
    changing = new_email.lower() != user.email.lower()

    if changing and email_taken(new_email, exclude_user=user):
        _consume(token)
        db.session.commit()
        return False, "That email address is now used by another account."

    if not _consume(token):
        db.session.rollback()
        return False, "That verification link has already been used."

    old_email = user.email
    user.email = new_email
    user.email_verified_at = datetime.utcnow()

    if changing:
        audit_service.record(
            "email_changed", actor=user, target=user, commit=False,
            details={"from_domain": old_email.rpartition("@")[2], "to_domain": new_email.rpartition("@")[2]}
        )
    else:
        audit_service.record("email_verified", actor=user, target=user, commit=False)

    db.session.commit()

    if changing:
        send_email(
            old_email,
            "Your COGNEXA email address was changed",
            f"Hi {user.username},\n\nThe email address on your COGNEXA account was changed "
            "from this address. If this wasn't you, contact support immediately.\n"
        )
        return True, "Email address updated and verified."

    return True, "Email verified. Thanks!"


def request_email_change(user, new_email, current_password):
    new_email = normalize_email(new_email)

    if not check_password(user, current_password):
        return False, "Your current password is incorrect."

    error = validate_email(new_email)
    if error:
        return False, error

    if new_email == user.email.lower():
        return False, "That's already your email address."

    if email_taken(new_email, exclude_user=user):
        return False, "That email address is already registered."

    if current_app.config.get("MAIL_BACKEND") == "disabled":
        return False, "Email changes are unavailable until email delivery is configured."

    send_verification_email(user, email=new_email)
    audit_service.record("email_change_requested", actor=user, target=user)

    return True, f"We sent a confirmation link to {new_email}. Your email changes once you open it."


def pending_email(user):
    token = (
        AccountToken.query
        .filter(
            AccountToken.user_id == user.id,
            AccountToken.purpose == PURPOSE_EMAIL_VERIFY,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > datetime.utcnow(),
            AccountToken.email.isnot(None),
            func.lower(AccountToken.email) != user.email.lower()
        )
        .order_by(AccountToken.created_at.desc())
        .first()
    )
    return token.email if token else None


# ------------------------------------------------------- password reset

def request_password_reset(email):
    """Always succeeds from the caller's point of view -- the response
    must be identical whether or not the address is registered."""

    user = find_user_by_email(email)

    if not user or not user.is_active:
        return

    recent = (
        AccountToken.query
        .filter(
            AccountToken.user_id == user.id,
            AccountToken.purpose == PURPOSE_PASSWORD_RESET,
            AccountToken.created_at > datetime.utcnow() - RESET_EMAIL_COOLDOWN
        )
        .first()
    )
    if recent:
        return

    raw_token = issue_token(user, PURPOSE_PASSWORD_RESET, email=user.email)
    link = external_url("auth.reset_password_landing", token=raw_token)
    minutes = current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"] // 60

    send_email(
        user.email,
        "Reset your COGNEXA password",
        f"Hi {user.username},\n\n"
        f"Someone asked to reset the password for your COGNEXA account. Use this link to choose a new one:\n{link}\n\n"
        f"The link works once and expires in {minutes} minutes. "
        "If you didn't ask for this, ignore this message -- your password won't change.\n"
    )


def reset_password(raw_token, new_password, confirm_password):
    token = get_valid_token(raw_token, PURPOSE_PASSWORD_RESET)

    if not token:
        return False, "That reset link is invalid or has expired. Request a new one."

    error = validate_password(new_password)
    if error:
        return False, error

    if new_password != confirm_password:
        return False, "Passwords do not match."

    if not _consume(token):
        db.session.rollback()
        return False, "That reset link has already been used."

    user = token.user
    _set_password(user, new_password)

    # The link was delivered to this address, so redeeming it proves the
    # user controls it -- as long as the address hasn't changed since.
    if not user.is_email_verified and token.email and token.email.lower() == user.email.lower():
        user.email_verified_at = datetime.utcnow()

    audit_service.record("password_reset", actor=user, target=user, commit=False)
    db.session.commit()

    return True, "Your password has been reset. You can log in now."


# -------------------------------------------------------------- profile

def favorite_game_choices():
    return [name for (name,) in Game.query.filter_by(is_active=True).with_entities(Game.name).order_by(Game.name).all()]


def update_profile(user, *, username, bio, country, favorite_game):
    """Only these four fields are editable here -- role, coins, XP,
    status and the rest are never read from the request."""

    username = (username or "").strip()
    bio = (bio or "").strip()
    country = (country or "").strip()
    favorite_game = (favorite_game or "").strip()

    if username != user.username:
        error = validate_username(username)
        if error:
            return False, error
        if username_taken(username, exclude_user=user):
            return False, "Username already exists."

    if len(bio) > BIO_MAX:
        return False, f"Bio must be at most {BIO_MAX} characters."

    if len(country) > COUNTRY_MAX:
        return False, f"Country must be at most {COUNTRY_MAX} characters."

    if favorite_game and favorite_game != user.favorite_game and favorite_game not in favorite_game_choices():
        return False, "Pick a favorite game from the list."

    old_username = user.username
    changed = {}
    for field, value in (("username", username), ("bio", bio), ("country", country), ("favorite_game", favorite_game)):
        if getattr(user, field) != value:
            changed[field] = value
            setattr(user, field, value)

    if not changed:
        return True, "No changes to save."

    if "username" in changed:
        audit_service.record("username_changed", actor=user, target=user, commit=False,
                             details={"from": old_username, "to": username})

    db.session.commit()

    return True, "Profile updated."
