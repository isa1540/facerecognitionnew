import os
from datetime import timedelta

class Config:
    # ======================
    # BASIC
    # ======================
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ======================
    # MYSQL (Railway)
    # ======================
    MYSQL_USER = os.getenv("MYSQLUSER")
    MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD")
    MYSQL_HOST = os.getenv("MYSQLHOST")
    MYSQL_PORT = os.getenv("MYSQLPORT", "3306")
    MYSQL_DB = os.getenv("MYSQLDATABASE")

    # ======================
    # UPLOAD / SESSION
    # ======================
    UPLOAD_FOLDER = "static/uploads"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    @classmethod
    def is_mysql_ready(cls) -> bool:
        return all([
            cls.MYSQL_USER,
            cls.MYSQL_PASSWORD,
            cls.MYSQL_HOST,
            cls.MYSQL_DB,
        ])

    @classmethod
    def build_database_uri(cls):
    # Railway
        database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_PUBLIC_URL")
    )

    if database_url:
        return database_url.replace(
            "mysql://",
            "mysql+mysqlconnector://",
            1
        )

    # Fallback ke SQLite jika tidak ada database Railway
    return "sqlite:///attendance.db"

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
