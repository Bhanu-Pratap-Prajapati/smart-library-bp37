import json

from flask import Blueprint, jsonify, request
from mysql.connector import Error

from db import db
from security import token_manager
from services.auth_service import AuthService
from services.book_service import BookService


ai_bp = Blueprint("ai", __name__, url_prefix="/api/ai")

BOOK_KEYWORDS = {
    "book",
    "books",
    "python",
    "dbms",
    "database",
    "recommend",
    "suggest",
    "search",
    "author",
    "title",
    "library",
    "trending",
}

USER_KEYWORDS = {
    "my",
    "issued",
    "issue",
    "fine",
    "dues",
    "due",
    "profile",
    "dashboard",
    "account",
}


def _extract_auth_user():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None

    is_valid, payload = token_manager.verify_token(token)
    if not is_valid:
        return None
    return payload


def _is_book_query(query_text):
    text = (query_text or "").strip().lower()
    return any(keyword in text for keyword in BOOK_KEYWORDS)


def _is_user_query(query_text):
    text = (query_text or "").strip().lower()
    if "my issued" in text or "fine details" in text:
        return True
    return any(keyword in text for keyword in USER_KEYWORDS)


def _get_user_fines(user_id):
    connection = None
    cursor = None
    try:
        BookService.ensure_library_schema()
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT t.id AS transaction_id,
                   t.fine_amount,
                   t.status,
                   b.title
            FROM transactions t
            INNER JOIN students s ON s.id = t.student_id
            INNER JOIN books b ON b.id = t.book_id
            WHERE s.user_id = %s
              AND t.fine_amount > 0
            ORDER BY t.id DESC
            LIMIT 12
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        fines = []
        for row in rows:
            fines.append(
                {
                    "transaction_id": row["transaction_id"],
                    "title": row["title"],
                    "fine_amount": f"Rs. {float(row.get('fine_amount') or 0):.2f}",
                    "status": str(row.get("status") or "").title(),
                }
            )
        return fines
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def _ensure_chat_history_schema():
    connection = None
    cursor = None
    try:
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                role ENUM('user', 'assistant') NOT NULL,
                message TEXT NOT NULL,
                response_payload JSON NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_chat_history_user_created (user_id, created_at),
                CONSTRAINT fk_chat_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        for statement in [
            "ALTER TABLE chat_history ADD COLUMN user_id INT NOT NULL",
            "ALTER TABLE chat_history ADD COLUMN role ENUM('user', 'assistant') NOT NULL DEFAULT 'user'",
            "ALTER TABLE chat_history ADD COLUMN message TEXT NOT NULL",
            "ALTER TABLE chat_history ADD COLUMN response_payload JSON NULL",
            "ALTER TABLE chat_history ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE chat_history ADD INDEX idx_chat_history_user_created (user_id, created_at)",
            "ALTER TABLE chat_history ADD CONSTRAINT fk_chat_history_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE",
        ]:
            try:
                cursor.execute(statement)
            except Error as exc:
                if getattr(exc, "errno", None) not in {1060, 1061, 1062, 1091, 1826}:
                    raise
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def _save_chat_entry(user_id, query, answer, response_payload):
    if not user_id:
        return

    connection = None
    cursor = None
    try:
        _ensure_chat_history_schema()
        connection = db.get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO chat_history (user_id, role, message, response_payload)
            VALUES (%s, 'user', %s, NULL)
            """,
            (user_id, query),
        )
        cursor.execute(
            """
            INSERT INTO chat_history (user_id, role, message, response_payload)
            VALUES (%s, 'assistant', %s, %s)
            """,
            (user_id, answer, json.dumps(response_payload or {})),
        )
        connection.commit()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


def _get_user_chat_history(user_id, limit=40):
    connection = None
    cursor = None
    try:
        _ensure_chat_history_schema()
        connection = db.get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, role, message, created_at
            FROM chat_history
            WHERE user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (user_id, int(limit)),
        )
        rows = cursor.fetchall() or []
        items = []
        for row in rows:
            items.append(
                {
                    "id": row["id"],
                    "role": row["role"],
                    "message": row["message"],
                    "timestamp": row["created_at"].isoformat() if row.get("created_at") else None,
                }
            )
        return list(reversed(items))
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


@ai_bp.get("/history")
def ai_history():
    auth_user = _extract_auth_user()
    if not auth_user or not auth_user.get("user_id"):
        return jsonify({"success": False, "message": "Authentication required.", "data": []}), 401

    try:
        entries = _get_user_chat_history(auth_user.get("user_id"))
        return jsonify({"success": True, "message": "Chat history loaded.", "data": entries}), 200
    except Exception as exc:
        return jsonify({"success": False, "message": f"Unable to load chat history: {exc}", "data": []}), 400


@ai_bp.post("/chat")
def ai_chat():
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    if not query:
        return jsonify({"success": False, "message": "query is required.", "data": None}), 400

    auth_user = _extract_auth_user()

    try:
        lowered = query.lower()
        response_status = 200
        response_message = "General response generated."
        response_data = None

        if _is_user_query(query):
            if not auth_user:
                response_message = "Authentication needed for user data queries."
                response_data = {
                    "type": "user",
                    "answer": "Please login to view your issued books, fine details, or profile information.",
                }
            elif "fine" in lowered or "dues" in lowered:
                fines = _get_user_fines(auth_user.get("user_id"))
                if fines:
                    response_message = "Fine details loaded."
                    response_data = {
                        "type": "user",
                        "answer": f"You have {len(fines)} fine record(s).",
                        "fines": fines,
                    }
                else:
                    response_message = "No fine records found."
                    response_data = {
                        "type": "user",
                        "answer": "No pending fine records were found for your account.",
                        "fines": [],
                    }
            elif "issued" in lowered or "issue" in lowered:
                success, message, issued_books = BookService.list_my_issued_books(
                    user_id=auth_user.get("user_id"),
                    role=auth_user.get("role"),
                )
                response_status = 200 if success else 400
                response_message = message
                response_data = {
                    "type": "user",
                    "answer": "These are your currently issued books." if issued_books else "No active issued books found.",
                    "issued_books": issued_books or [],
                }
            else:
                success, message, profile = AuthService.get_profile(auth_user.get("user_id"))
                display_name = (profile or {}).get("full_name") or "User"
                response_status = 200 if success else 400
                response_message = message
                response_data = {
                    "type": "user",
                    "answer": f"Hello {display_name}. Your account role is {(profile or {}).get('role', '-')} and email is {(profile or {}).get('email', '-')}.",
                    "user": profile or {},
                }
        elif _is_book_query(query):
            success, message, books = BookService.search_and_store_book(query_text=query)
            if not books:
                rec_success, rec_message, recommendations = BookService.get_recommendations(query_text=query, limit=8)
                response_status = 200 if rec_success else 400
                response_message = rec_message
                response_data = {
                    "type": "books",
                    "answer": "Here are some recommended books you can explore.",
                    "books": recommendations or [],
                }
            else:
                response_status = 200 if success else 400
                response_message = message
                response_data = {
                    "type": "books",
                    "answer": f"I found {len(books)} relevant book(s).",
                    "books": books,
                }
        else:
            response_data = {
                "type": "general",
                "answer": (
                    "I can help with book discovery, recommendations, issued books, and fine details. "
                    "Try asking: Best python books, Suggest DBMS books, My issued books, or Fine details."
                ),
            }

        if auth_user and auth_user.get("user_id") and response_status == 200 and response_data:
            _save_chat_entry(
                user_id=auth_user.get("user_id"),
                query=query,
                answer=str(response_data.get("answer") or ""),
                response_payload=response_data,
            )

        return jsonify({"success": response_status == 200, "message": response_message, "data": response_data}), response_status
    except Exception as exc:
        return jsonify({"success": False, "message": f"Unable to process AI chat request: {exc}", "data": None}), 400
