from flask import Blueprint, jsonify, request

from routes.auth_routes import require_auth
from services.book_service import BookService


students_bp = Blueprint("students", __name__, url_prefix="/api/students")


@students_bp.get("")
@require_auth
def get_students():
    auth_user = request.auth_user
    if (auth_user.get("role") or "").strip().lower() not in {"admin", "librarian"}:
        return jsonify({"success": False, "message": "Only admin/librarian can access students.", "data": []}), 403
    success, message, data = BookService.list_students()
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@students_bp.post("")
@require_auth
def create_student():
    auth_user = request.auth_user
    if (auth_user.get("role") or "").strip().lower() not in {"admin", "librarian"}:
        return jsonify({"success": False, "message": "Only admin/librarian can create students.", "data": None}), 403
    payload = request.get_json(silent=True) or {}
    success, message, data = BookService.create_student(
        name=payload.get("name"),
        email=payload.get("email"),
        user_id=payload.get("user_id"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (201 if success else 400)
