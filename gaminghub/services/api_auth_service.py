import hashlib
import secrets
from datetime import datetime

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

    raw_token = secrets.token_hex(32)

    db.session.add(ApiToken(user_id=user.id, token_hash=_hash(raw_token)))
    db.session.commit()

    return raw_token


def get_user_for_token(raw_token):
    if not raw_token:
        return None

    token_row = ApiToken.query.filter_by(token_hash=_hash(raw_token)).first()

    if not token_row:
        return None

    token_row.last_used_at = datetime.utcnow()
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
