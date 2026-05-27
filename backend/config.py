from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Config:
    host: str = os.getenv("DB_HOST", "gateway01.ap-southeast-1.prod.aws.tidbcloud.com")
    port: int = int(os.getenv("DB_PORT", "4000"))
    user: str = os.getenv("DB_USER", "3BYzR4cFGmPw4a4.root")
    password: str = os.getenv("DB_PASSWORD", "WdkV3aug7TwuYkN3")
    database: str = os.getenv("DB_DATABASE", "smart_library")
    secret_key: str = os.getenv("SECRET_KEY", "smart-library-secret")
    jwt_secret: str = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "smart-library-secret"))
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_hours: int = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))
    admin_registration_key: str = os.getenv("ADMIN_REGISTRATION_KEY", "smart-admin-key")
    primary_admin_name: str = os.getenv("PRIMARY_ADMIN_NAME", "")
    primary_admin_email: str = os.getenv("PRIMARY_ADMIN_EMAIL", "")
    primary_admin_password: str = os.getenv("PRIMARY_ADMIN_PASSWORD", "")
    backend_url: str = os.getenv("BACKEND_URL", "https://smart-library-backend-ngj7.onrender.com")
    frontend_url: str = os.getenv("FRONTEND_URL", "https://smart-library-bp37.vercel.app/")
    frontend_login_path: str = os.getenv("FRONTEND_LOGIN_PATH", "/frontend/pages/login.html")
    debug: bool = os.getenv("FLASK_DEBUG", "true").lower() == "true"


config = Config()
