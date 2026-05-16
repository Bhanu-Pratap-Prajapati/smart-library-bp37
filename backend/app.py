import site
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
for extra_path in (BASE_DIR / "_vendor", Path(site.getusersitepackages())):
    path_str = str(extra_path)
    try:
        should_add = extra_path.exists() and path_str not in sys.path
    except OSError:
        should_add = False
    if should_add:
        sys.path.insert(0, path_str)

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from config import config
from db import db
from routes.auth_routes import auth_bp, auth_public_bp
from routes.ai_routes import ai_bp
from routes.book_routes import books_bp
from routes.student_routes import students_bp

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = config.secret_key
CORS(app, resources={r"/api/*": {"origins": "*"}}, allow_headers=["Content-Type", "Authorization"])
app.register_blueprint(auth_bp)
app.register_blueprint(auth_public_bp)
app.register_blueprint(books_bp)
app.register_blueprint(students_bp)
app.register_blueprint(ai_bp)


@app.get("/")
def index():
    return jsonify({
        "project": "Smart Library Management System",
        "message": "Backend service is live.",
        "available_routes": [
            "/api/health",
            "/api/db-status",
            "/api/register",
            "/api/signup",
            "/api/login",
            "/api/me/dashboard",
            "/api/me/profile",
            "/api/books",
            "/api/books/search?q=atomic%20habits",
            "/api/books/issue",
            "/api/books/return",
            "/api/students",
            "/api/ai/chat",
        ],
    })


@app.get("/api/db-status")
def database_status():
    connected, message = db.test_connection()
    status_code = 200 if connected else 500
    return jsonify({"connected": connected, "message": message}), status_code


if __name__ == "__main__":
    app.run(debug=config.debug, host="127.0.0.1", port=5000)
