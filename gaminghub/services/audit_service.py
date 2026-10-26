import json
import logging

from flask import has_request_context, request

from gaminghub.database.database import db
from gaminghub.models.audit_log import AuditLog

logger = logging.getLogger("gaminghub.audit")


def record(action, *, actor=None, target=None, target_type=None, target_label=None,
           reason=None, details=None, commit=True):
    """
    Appends one audit entry. `target` may be any model instance with an
    id; target_type/target_label default from it. details must never
    contain secrets -- it's shown to admins verbatim.
    """

    if target is not None:
        target_type = target_type or target.__tablename__.rstrip("s")
        target_label = target_label or getattr(target, "username", None) or getattr(target, "name", None)

    entry = AuditLog(
        actor_id=actor.id if actor is not None else None,
        actor_username=actor.username if actor is not None else None,
        action=action,
        target_type=target_type,
        target_id=target.id if target is not None else None,
        target_label=(target_label or "")[:120] or None,
        reason=(reason or "")[:255] or None,
        details=json.dumps(details, sort_keys=True, default=str) if details else None,
        ip_address=request.remote_addr if has_request_context() else None,
    )

    db.session.add(entry)

    if commit:
        db.session.commit()

    logger.info(
        "audit action=%s actor_id=%s target=%s:%s",
        action, entry.actor_id, entry.target_type, entry.target_id
    )

    return entry


def list_entries(*, action=None, page=1, per_page=50):
    query = AuditLog.query

    if action:
        query = query.filter_by(action=action)

    return query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )


def list_actions():
    return [a for (a,) in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()]


def entries_for_user(user, limit=20):
    return (
        AuditLog.query
        .filter((AuditLog.target_type == "user") & (AuditLog.target_id == user.id))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )


def parse_details(entry):
    if not entry.details:
        return {}
    try:
        return json.loads(entry.details)
    except ValueError:
        return {}
