import logging

from flask import Blueprint, jsonify
from sqlalchemy import text

from gaminghub.database.database import db

health = Blueprint("health", __name__)

logger = logging.getLogger(__name__)


@health.route("/healthz")
def healthz():
    """Liveness + database check for load balancers and container
    orchestrators. Deliberately says nothing about versions, hosts or
    the error itself -- that goes to the log, not the response."""

    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unavailable")
        db.session.rollback()
        return jsonify({"status": "unavailable"}), 503

    return jsonify({"status": "ok"})
