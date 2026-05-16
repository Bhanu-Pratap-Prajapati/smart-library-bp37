from functools import wraps

from flask import Blueprint, jsonify, request

from security import token_manager
from services.auth_service import AuthService


auth_bp = Blueprint("auth", __name__, url_prefix="/api")
auth_public_bp = Blueprint("auth_public", __name__)


def _extract_bearer_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def require_auth(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return jsonify({"success": False, "message": "Authentication required."}), 401
        is_valid, payload = token_manager.verify_token(token)
        if not is_valid:
            return jsonify({"success": False, "message": payload}), 401
        request.auth_user = payload
        return view_func(*args, **kwargs)
    return wrapper


@auth_bp.get("/health")
def health_check():
    return jsonify({"status": "ok", "message": "Smart Library backend is running."}), 200


@auth_bp.get("/auth/demo-users")
def demo_users():
    success, message, data = AuthService.get_demo_users()
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    success, message, data = AuthService.register_user(
        full_name=payload.get("full_name"),
        email=payload.get("email"),
        password=payload.get("password"),
        role=payload.get("role"),
        admin_key=payload.get("admin_key"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (201 if success else 400)


@auth_bp.post("/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    success, message, data = AuthService.register_user(
        full_name=payload.get("name") or payload.get("full_name"),
        email=payload.get("email"),
        password=payload.get("password"),
        role=payload.get("role") or "student",
        admin_key=payload.get("admin_key"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (201 if success else 400)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    success, message, user, token = AuthService.login_user(
        email=payload.get("email"),
        password=payload.get("password"),
    )
    return jsonify({"success": success, "message": message, "user": user, "token": token}), (200 if success else 401)


@auth_public_bp.post("/signup")
def signup_alias():
    return signup()


@auth_public_bp.post("/login")
def login_alias():
    return login()


@auth_bp.post("/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    success, message, data = AuthService.request_password_reset(
        email=payload.get("email"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@auth_bp.post("/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    success, message = AuthService.reset_password(
        email=payload.get("email"),
        reset_token=payload.get("reset_token"),
        new_password=payload.get("new_password"),
    )
    return jsonify({"success": success, "message": message}), (200 if success else 400)


@auth_bp.get("/me/dashboard")
@require_auth
def my_dashboard():
    auth_user = request.auth_user
    success, message, data = AuthService.get_dashboard_data(auth_user["user_id"], auth_user["role"])
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@auth_bp.get("/me/profile")
@require_auth
def my_profile():
    auth_user = request.auth_user
    success, message, data = AuthService.get_profile(auth_user["user_id"])
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@auth_bp.patch("/me/profile")
@require_auth
def update_my_profile():
    auth_user = request.auth_user
    payload = request.get_json(silent=True) or {}
    success, message, data = AuthService.update_profile(
        user_id=auth_user["user_id"],
        bio=payload.get("bio"),
        profile_image_url=payload.get("profile_image_url"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@auth_bp.patch("/admin/users/<int:target_user_id>/status")
@require_auth
def update_user_status(target_user_id):
    auth_user = request.auth_user
    payload = request.get_json(silent=True) or {}
    success, message, data = AuthService.update_user_status(
        admin_user_id=auth_user["user_id"],
        target_user_id=target_user_id,
        new_status=payload.get("status"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)
