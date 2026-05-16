from flask import Blueprint, jsonify, request

from routes.auth_routes import require_auth
from services.book_service import BookService


books_bp = Blueprint("books", __name__, url_prefix="/api/books")


@books_bp.get("")
def get_books():
    refresh = (request.args.get("refresh") or "false").strip().lower() == "true"
    success, message, data = BookService.get_books(refresh=refresh)
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.post("/refresh")
def refresh_books():
    success, message, data = BookService.get_books(refresh=True)
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.get("/search")
def search_books():
    query = (request.args.get("q") or "").strip()
    try:
        success, message, data = BookService.search_and_store_book(query)
        return jsonify({"success": success, "message": message, "data": data}), 200
    except ValueError as exc:
        return jsonify({"success": False, "message": str(exc), "data": []}), 400
    except Exception as exc:
        return jsonify({"success": False, "message": f"Unable to search books: {exc}", "data": []}), 400


@books_bp.get("/suggestions")
def search_suggestions():
    query = (request.args.get("q") or "").strip()
    success, message, data = BookService.get_search_suggestions(query)
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.get("/recommendations")
def get_recommendations():
    query = (request.args.get("q") or "").strip()
    success, message, data = BookService.get_recommendations(query)
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.get("/my-issued")
@require_auth
def my_issued_books():
    auth_user = request.auth_user
    success, message, data = BookService.list_my_issued_books(
        user_id=auth_user.get("user_id"),
        role=auth_user.get("role"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.get("/due-check")
@require_auth
def due_check_books():
    auth_user = request.auth_user
    success, message, data = BookService.list_due_books(
        user_id=auth_user.get("user_id"),
        role=auth_user.get("role"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.post("/issue")
@require_auth
def issue_book():
    payload = request.get_json(silent=True) or {}
    auth_user = request.auth_user
    success, message, data = BookService.issue_book(
        book_id=payload.get("book_id"),
        student_id=payload.get("student_id"),
        issue_date=payload.get("issue_date"),
        due_date=payload.get("due_date"),
        issuer_user_id=auth_user.get("user_id"),
        issuer_role=auth_user.get("role"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.post("/return")
@require_auth
def return_book():
    payload = request.get_json(silent=True) or {}
    auth_user = request.auth_user
    success, message, data = BookService.return_book(
        book_id=payload.get("book_id"),
        current_date=payload.get("current_date"),
        transaction_id=payload.get("transaction_id"),
        requester_user_id=auth_user.get("user_id"),
        requester_role=auth_user.get("role"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.post("/pay-fine")
@require_auth
def pay_fine():
    payload = request.get_json(silent=True) or {}
    auth_user = request.auth_user
    success, message, data = BookService.pay_fine(
        transaction_id=payload.get("transaction_id"),
        paid_by_user_id=auth_user.get("user_id"),
        amount=payload.get("amount"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.post("/admin/add")
@require_auth
def admin_add_book():
    auth_user = request.auth_user
    if (auth_user.get("role") or "").strip().lower() not in {"admin", "librarian"}:
        return jsonify({"success": False, "message": "Only admin/librarian can add books.", "data": None}), 403

    payload = request.get_json(silent=True) or {}
    success, message, data = BookService.add_book(
        title=payload.get("title"),
        author_name=payload.get("author_name"),
        category=payload.get("category"),
        total_copies=payload.get("total_copies"),
        description=payload.get("description"),
        published_date=payload.get("published_date"),
        isbn=payload.get("isbn"),
        cover_url=payload.get("cover_url"),
    )
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)


@books_bp.delete("/admin/<int:book_id>")
@require_auth
def admin_remove_book(book_id):
    auth_user = request.auth_user
    if (auth_user.get("role") or "").strip().lower() not in {"admin", "librarian"}:
        return jsonify({"success": False, "message": "Only admin/librarian can remove books.", "data": None}), 403

    success, message, data = BookService.remove_book(book_id)
    return jsonify({"success": success, "message": message, "data": data}), (200 if success else 400)
