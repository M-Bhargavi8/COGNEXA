"""
Production entry point. Point the WSGI server at `wsgi:app`, e.g.

    waitress-serve --listen=0.0.0.0:8000 wsgi:app

APP_ENV defaults to "production" here (unlike app.py, the development
entry point), so a deployment that forgets to set it still gets the
strict configuration checks rather than development defaults.
"""

import os

os.environ.setdefault("APP_ENV", "production")

from gaminghub import create_app  # noqa: E402

app = create_app()
