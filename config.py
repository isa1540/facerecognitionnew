import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = "static/uploads"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    @classmethod
    def build_database_uri(cls):
        database_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("MYSQL_URL")
            or os.getenv("MYSQL_PUBLIC_URL")
        )

        if database_url:
            if database_url.startswith("mysql://"):
                return database_url.replace(
                    "mysql://",
                    "mysql+mysqlconnector://",
                    1
                )
            return database_url

        raise Exception("DATABASE_URL not found")

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)