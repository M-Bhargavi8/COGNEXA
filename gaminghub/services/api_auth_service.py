import hashlib
import secrets
from datetime import datetime, timedelta

from flask import current_app

from gaminghub.database.database import db
from gaminghub.models.api_token import ApiToken


def _hash(raw_token):
    # The token itself is 256 bits of randomness -- unlike a password, it
    # doesn't need a slow, salted hash to resist guessing. A fast digest
    # is standard practice for high-entropy API tokens.
    return hashlib.sha256(raw_token.encode()).hexdigest()


def issue_token(user):
    """Creates a new token for user and returns the raw value. This is the
    only time the raw token is ever available -- only its hash is stored."""

    raw_token, _ = issue_token_with_expiry(user)
    return raw_token


def issue_token_with_expiry(user):
    """Like issue_token(), but returns (raw_token, expires_at)."""

    raw_token = secrets.token_hex(32)
    now = datetime.utcnow()

    # Housekeeping: expired tokens can never authenticate again.
    ApiToken.query.filter(ApiToken.user_id == user.id, ApiToken.expires_at <= now).delete()

    ttl_days = current_app.config.get("API_TOKEN_TTL_DAYS", 30)
    expires_at = now + timedelta(days=ttl_days) if ttl_days else None

    db.session.add(ApiToken(user_id=user.id, token_hash=_hash(raw_token), created_at=now, expires_at=expires_at))
    db.session.commit()

    return raw_token, expires_at


def get_user_for_token(raw_token):
    if not raw_token:
        return None

    token_row = ApiToken.query.filter_by(token_hash=_hash(raw_token)).first()

    if not token_row:
        return None

    now = datetime.utcnow()

    if token_row.expires_at is not None and token_row.expires_at <= now:
        return None

    if not token_row.user or not token_row.user.is_active:
        return None

    token_row.last_used_at = now
    db.session.commit()

    return token_row.user


def revoke_token(raw_token):
    """Returns True if a matching token was found and revoked."""

    token_row = ApiToken.query.filter_by(token_hash=_hash(raw_token)).first()

    if not token_row:
        return False

    db.session.delete(token_row)
    db.session.commit()

    return True
