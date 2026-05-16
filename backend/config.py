from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Config:
    host: str = os.getenv("MYSQL_HOST", "localhost")
    port: int = int(os.getenv("MYSQL_PORT", "3306"))
    user: str = os.getenv("MYSQL_USER", "root")
    password: str = os.getenv("MYSQL_PASSWORD", "")
    database: str = os.getenv("MYSQL_DATABASE", "smart_library")
    secret_key: str = os.getenv("SECRET_KEY", "smart-library-secret")
    jwt_secret: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "smart-library-secret"))
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    admin_registration_key: str = os.getenv("ADMIN_REGISTRATION_KEY", "smart-admin-key")
    primary_admin_name: str = os.getenv("PRIMARY_ADMIN_NAME", "")
    primary_admin_email: str = os.getenv("PRIMARY_ADMIN_EMAIL", "")
    primary_admin_password: str = os.getenv("PRIMARY_ADMIN_PASSWORD", "")
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:5000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    frontend_login_path: str = os.getenv("FRONTEND_LOGIN_PATH", "/frontend/pages/login.html")
    debug: bool = os.getenv("FLASK_DEBUG", "true").lower() == "true"


config = Config()
