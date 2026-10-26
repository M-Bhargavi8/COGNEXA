"""
Application logging: one line per record on stdout, which is what
container platforms and process managers collect. Production emits JSON
(machine-parseable); development emits readable text.

Request logs record the matched route pattern ("/reset-password/<token>")
rather than the raw path, so tokens that travel in URLs never reach the
logs, and never include query strings, form data or headers.
"""

import json
import logging
import re
import sys
import time
import uuid

from flask import g, has_request_context, request

APP_LOGGER = "gaminghub"

# An inbound X-Request-ID (from a proxy) is reused only if it's a plain
# token -- anything else could inject fake lines into text logs.
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key in ("method", "route", "status", "duration_ms", "remote_addr"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(app):
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())

    if app.config.get("APP_ENV") == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"
        ))

    logger = logging.getLogger(APP_LOGGER)
    # create_app() runs once per test; replacing (not appending) keeps
    # one handler instead of one per app instance.
    for existing in list(logger.handlers):
        logger.removeHandler(existing)
    logger.addHandler(handler)
    logger.setLevel(level)

    if app.config.get("TESTING"):
        return

    request_logger = logging.getLogger(APP_LOGGER + ".request")

    @app.before_request
    def _start_request():
        inbound = request.headers.get("X-Request-ID", "")
        g.request_id = inbound if _REQUEST_ID_RE.match(inbound) else uuid.uuid4().hex
        g.request_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        if request.path.startswith("/static/"):
            return response

        duration_ms = round((time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000, 1)
        route = request.url_rule.rule if request.url_rule else "<unmatched>"

        request_logger.info(
            "%s %s %s %sms", request.method, route, response.status_code, duration_ms,
            extra={
                "method": request.method, "route": route, "status": response.status_code,
                "duration_ms": duration_ms, "remote_addr": request.remote_addr,
            },
        )
        response.headers["X-Request-ID"] = g.get("request_id", "")
        return response
