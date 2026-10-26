import logging

from flask import Blueprint, jsonify
from sqlalchemy import text

from gaminghub.database.database import db, limiter

health = Blueprint("health", __name__)

logger = logging.getLogger(__name__)


@health.route("/healthz")
def healthz():
    """Liveness + dependency check for load balancers and container
    orchestrators. Deliberately says nothing about versions, hosts or
    the error itself -- that goes to the log, not the response.

    503 when the database is unreachable (nothing works without it).
    200 "degraded" when only the shared rate-limit storage is down: the
    app keeps serving with per-process limits, but someone should look.
    """

    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unavailable")
        db.session.rollback()
        return jsonify({"status": "unavailable"}), 503

    if not _rate_limit_storage_ok():
        return jsonify({"status": "degraded"})

    return jsonify({"status": "ok"})


def _rate_limit_storage_ok():
    if not limiter.enabled:
        return True

    storage = limiter.storage
    if type(storage).__name__ == "MemoryStorage":
        return True

    try:
        healthy = bool(storage.check())
    except Exception:
        healthy = False

    if not healthy:
        logger.error("Health check: rate-limit storage unreachable; using in-memory fallback")

    return healthy
