from datetime import datetime
from gaminghub.database.database import db


class ApiToken(db.Model):
    __tablename__ = "api_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship("User")

    # sha256 hex digest of the real token -- only the hash is ever stored,
    # the raw token is shown once at issuance and can't be recovered later.
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<ApiToken user={self.user_id}>"
