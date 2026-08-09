import os

class Config:
    SECRET_KEY = "GamingHubSecretKey"

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
    os.makedirs(INSTANCE_DIR, exist_ok=True)

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
    BASE_DIR,
    "gaminghub",
    "database",
    "gaming.db"
)

    SQLALCHEMY_TRACK_MODIFICATIONS = False