import os
import secrets

from dotenv import load_dotenv

load_dotenv()


def _get_or_create_secret_key(instance_dir):
    """
    A real SECRET_KEY signs both session cookies and CSRF tokens -- a
    hardcoded one checked into source control means anyone who reads the
    code can forge either. SECRET_KEY in the environment always wins (the
    real path for production); otherwise a random key is generated once
    and persisted in the (gitignored) instance folder, so dev sessions
    survive restarts without ever committing a real secret.
    """

    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key

    key_path = os.path.join(instance_dir, "secret_key")

    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()

    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)

    return key


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    SECRET_KEY = _get_or_create_secret_key(INSTANCE_DIR)

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
    BASE_DIR,
    "gaminghub",
    "database",
    "gaming.db"
)

    SQLALCHEMY_TRACK_MODIFICATIONS = False