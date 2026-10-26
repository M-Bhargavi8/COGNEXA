from datetime import datetime
from gaminghub.database.database import db


PURPOSE_EMAIL_VERIFY = "email_verify"
PURPOSE_PASSWORD_RESET = "password_reset"


class AccountToken(db.Model):
    """
    Single-use, expiring tokens sent by email (verification, password
    reset). Like ApiToken, only a sha256 of the raw token is stored --
    a database leak doesn't hand out working reset links.
    """

    __tablename__ = "account_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User")

    purpose = db.Column(db.String(30), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # For email_verify: the address being verified. It can differ from
    # user.email while an email change is pending -- the new address
    # only replaces the old one once this token is redeemed.
    email = db.Column(db.String(120))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<AccountToken {self.purpose} user={self.user_id}>"
