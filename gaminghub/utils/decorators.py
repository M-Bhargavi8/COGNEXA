from functools import wraps

from flask import abort, g, jsonify, request
from flask_login import current_user

from gaminghub.services import api_auth_service


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)

        return view(*args, **kwargs)

    return wrapped


def api_token_required(view):
    """
    Authenticates REST API requests via an 'Authorization: Bearer <token>'
    header instead of the session cookie current_user relies on -- a
    non-browser client has no session. Sets g.api_user/g.api_token on
    success; a view under this decorator should use those, not
    current_user.
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header. Expected: Bearer <token>"}), 401

        raw_token = auth_header[len("Bearer "):].strip()
        user = api_auth_service.get_user_for_token(raw_token)

        if not user:
            return jsonify({"error": "Invalid or revoked API token."}), 401

        g.api_user = user
        g.api_token = raw_token

        return view(*args, **kwargs)

    return wrapped
