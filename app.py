"""
Development entry point: `python app.py`. Production uses wsgi.py with a
real WSGI server instead -- see docs/DEPLOYMENT.md.
"""

import os

from gaminghub import create_app

app = create_app()

if __name__ == "__main__":
    if app.config.get("APP_ENV") == "production":
        raise SystemExit("app.py is the development server. Run production with: waitress-serve wsgi:app")

    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug)
