from datetime import datetime
from gaminghub.database.database import db


class AuditLog(db.Model):
    """
    Append-only record of administrative and security-sensitive actions.
    No route updates or deletes these rows. The actor's username is
    copied in so the entry still reads correctly if that account is later
    renamed. Never store passwords, tokens or other secrets in details.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    actor_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    actor_username = db.Column(db.String(50))

    action = db.Column(db.String(50), nullable=False, index=True)

    target_type = db.Column(db.String(30))
    target_id = db.Column(db.Integer)
    target_label = db.Column(db.String(120))

    reason = db.Column(db.String(255))
    details = db.Column(db.Text)  # JSON
    ip_address = db.Column(db.String(45))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} by={self.actor_id}>"
