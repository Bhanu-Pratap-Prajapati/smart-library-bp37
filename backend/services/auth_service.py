import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import bcrypt
from mysql.connector import Error

from db import db
from security import token_manager
from services.book_service import BookService

VALID_ROLES = {"student", "librarian", "admin"}
PUBLIC_ROLES = {"student", "librarian"}
ROLE_TITLES = {
    "student": "Student Member",
    "librarian": "Library Librarian",
    "admin": "System Administrator",
}
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PASSWORD_SPECIAL_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9]")
DEMO_USERS = [
    {"full_name": "Aarav Sharma", "email": "student1@smartlibrary.demo", "password": "Student@123", "role": "student", "department": "Computer Science", "bio": "Demo student account for testing the library login system.", "avatar_color": "#f97316"},
    {"full_name": "Priya Verma", "email": "student2@smartlibrary.demo", "password": "Student@123", "role": "student", "department": "Economics", "bio": "Demo student account focused on economics and research resources.", "avatar_color": "#0ea5e9"},
    {"full_name": "Meera Iyer", "email": "student3@smartlibrary.demo", "password": "Student@123", "role": "student", "department": "History", "bio": "Demo student account for humanities and history collections.", "avatar_color": "#8b5cf6"},
    {"full_name": "Rohan Singh", "email": "librarian@smartlibrary.demo", "password": "Librarian@123", "role": "librarian", "department": "Circulation Desk", "bio": "Demo librarian account for catalog and desk operations.", "avatar_color": "#14b8a6"},
]


class AuthService:
    @staticmethod
    def _membership_code(role):
        return f"{role[:3].upper()}-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _format_decimal(value):
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)

    @staticmethod
    def _normalize_role(role):
        return (role or "").strip().lower()

    @staticmethod
    def _normalize_email(email):
        return (email or "").strip().lower()

    @staticmethod
    def _validate_email(email):
        if not EMAIL_PATTERN.match(email or ""):
            return False, "Please enter a valid email address."
        return True, ""

    @staticmethod
    def _validate_password_strength(password):
        password = password or ""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r"[A-Z]", password):
            return False, "Password must include at least one uppercase letter."
        if not re.search(r"[a-z]", password):
            return False, "Password must include at least one lowercase letter."
        if not re.search(r"\d", password):
            return False, "Password must include at least one number."
        if not PASSWORD_SPECIAL_CHAR_PATTERN.search(password):
            return False, "Password must include at least one special character."
        return True, ""

    @staticmethod
    def _hash_password(password):
        return bcrypt.hashpw((password or "").encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_password(password, password_hash):
        try:
            return bcrypt.checkpw((password or "").encode("utf-8"), (password_hash or "").encode("utf-8"))
        except ValueError:
            return False

    @staticmethod
    def _create_user_profile_for_new_user(cursor, user_id, role, department, bio, avatar_color):
        cursor.execute(
            "INSERT INTO user_profiles (user_id, membership_code, profession_title, department, bio, profile_image_url, joined_on, avatar_color) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                user_id,
                AuthService._membership_code(role),
                ROLE_TITLES[role],
                department,
                bio,
                "",
                date.today(),
                avatar_color,
            ),
        )

    @staticmethod
    def _query_profile(cursor, user_id):
        cursor.execute(
            "SELECT u.id, u.full_name, u.email, u.role, u.last_login, p.membership_code, p.profession_title, p.department, p.bio, p.profile_image_url, p.joined_on, p.avatar_color FROM users u JOIN user_profiles p ON p.user_id = u.id WHERE u.id = %s",
            (user_id,),
        )
        return cursor.fetchone()

    @staticmethod
    def _safe_user(user):
        return {
            "id": user["id"],
            "name": user["full_name"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"],
        }

    @staticmethod
    def _build_student_notifications(active_loans):
        notifications = []
        now = datetime.now()
        due_soon_window = now + timedelta(days=2)

        for loan in active_loans:
            issued_at = loan.get("issued_at_raw")
            due_at = loan.get("due_at_raw")
            if not due_at:
                continue

            level = "issued"
            title = "Book Issued"
            message = f"'{loan['title']}' was issued to you. Due on {loan['due_at']}."

            if due_at < now:
                level = "overdue"
                title = "Overdue Book"
                message = f"'{loan['title']}' is overdue. Please return it as soon as possible."
            elif due_at <= due_soon_window:
                level = "due_soon"
                title = "Due Date Reminder"
                message = f"'{loan['title']}' is due soon on {loan['due_at']}."
            elif issued_at and (now - issued_at) <= timedelta(days=1):
                level = "issued"
                title = "Book Issued"
                message = f"'{loan['title']}' was issued to you. Due on {loan['due_at']}."
            else:
                continue

            notifications.append(
                {
                    "level": level,
                    "title": title,
                    "message": message,
                    "book_id": loan["book_id"],
                    "transaction_id": loan["transaction_id"],
                    "can_return": True,
                }
            )

        order = {"overdue": 0, "due_soon": 1, "issued": 2}
        notifications.sort(key=lambda item: order.get(item["level"], 9))
        return notifications[:12]

    @staticmethod
    def update_user_status(admin_user_id, target_user_id, new_status):
        new_status = (new_status or "").strip().lower()
        if new_status not in {"active", "inactive"}:
            return False, "Status must be either active or inactive.", None

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute("SELECT id, role, account_status FROM users WHERE id = %s", (admin_user_id,))
            admin_user = cursor.fetchone()
            if not admin_user or admin_user["role"] != "admin":
                return False, "Only admins can update user status.", None

            if int(admin_user_id) == int(target_user_id):
                return False, "Admin cannot change their own account status.", None

            cursor.execute("SELECT id, role, full_name, account_status FROM users WHERE id = %s", (target_user_id,))
            target_user = cursor.fetchone()
            if not target_user:
                return False, "Target user not found.", None

            if target_user["account_status"] == new_status:
                return False, f"User is already {new_status}.", None

            if target_user["role"] == "admin" and new_status == "inactive":
                cursor.execute("SELECT COUNT(*) AS total_admins FROM users WHERE role = 'admin' AND account_status = 'active'")
                active_admins = cursor.fetchone()
                if int(active_admins["total_admins"] or 0) <= 1:
                    return False, "At least one active admin must remain in the system.", None

            cursor.execute(
                "UPDATE users SET account_status = %s WHERE id = %s",
                (new_status, target_user_id),
            )
            connection.commit()
            success, message, data = AuthService.get_dashboard_data(admin_user_id, "admin")
            if not success:
                return False, message, None
            return True, f"{target_user['full_name']} marked as {new_status}.", data
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def get_demo_users():
        demo_rows = [
            {"full_name": user["full_name"], "email": user["email"], "password": user["password"], "role": user["role"].title(), "department": user["department"]}
            for user in DEMO_USERS
        ]
        return True, "Demo users loaded successfully.", demo_rows

    @staticmethod
    def register_user(full_name, email, password, role, admin_key=None):
        normalized_role = AuthService._normalize_role(role)
        normalized_email = AuthService._normalize_email(email)
        full_name = (full_name or "").strip()

        if normalized_role not in PUBLIC_ROLES:
            return False, "Admin account cannot be created from public registration.", None
        if len(full_name) < 3:
            return False, "Full name must be at least 3 characters long.", None
        is_email_valid, email_message = AuthService._validate_email(normalized_email)
        if not is_email_valid:
            return False, email_message, None
        is_password_valid, password_message = AuthService._validate_password_strength(password)
        if not is_password_valid:
            return False, password_message, None

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (normalized_email,))
            if cursor.fetchone():
                return False, "This email is already registered. Please sign in instead.", None

            cursor.execute(
                "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (full_name, normalized_email, AuthService._hash_password(password), normalized_role),
            )
            user_id = cursor.lastrowid
            AuthService._create_user_profile_for_new_user(
                cursor=cursor,
                user_id=user_id,
                role=normalized_role,
                department="General",
                bio="New member profile. Update your bio from the dashboard.",
                avatar_color="#f97316",
            )
            connection.commit()
            if normalized_role == "student":
                BookService.sync_student_from_user(user_id, full_name, normalized_email)
            return True, "Account created successfully. You can now sign in.", {"user_id": user_id}
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def login_user(email, password):
        normalized_email = AuthService._normalize_email(email)
        is_email_valid, email_message = AuthService._validate_email(normalized_email)
        if not is_email_valid:
            return False, email_message, None, None

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT id, full_name, email, password_hash, role, account_status, google_id FROM users WHERE email = %s",
                (normalized_email,),
            )
            user = cursor.fetchone()
            if not user:
                return False, "No account found for this email.", None, None
            if user["account_status"] != "active":
                return False, "This account is inactive. Please contact the administrator.", None, None
            if not AuthService._verify_password(password, user["password_hash"]):
                return False, "Incorrect email or password.", None, None

            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
            connection.commit()
            if user["role"] == "student":
                # Ensure older student accounts are always linked for issue/return flows.
                BookService.sync_student_from_user(user["id"], user["full_name"], user["email"])
            return True, "Login successful.", AuthService._safe_user(user), token_manager.create_token(user["id"], user["role"])
        except Error as exc:
            return False, f"Database error: {exc}", None, None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def request_password_reset(email):
        normalized_email = AuthService._normalize_email(email)
        is_email_valid, email_message = AuthService._validate_email(normalized_email)
        if not is_email_valid:
            return False, email_message, None

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, email, role FROM users WHERE email = %s", (normalized_email,))
            user = cursor.fetchone()
            if not user:
                return False, "No account found for this email.", None

            reset_token = token_manager.create_password_reset_token(normalized_email, user["role"])
            return True, "Password reset approved. Set your new password below.", {
                "reset_token": reset_token,
                "email": normalized_email,
            }
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def reset_password(email, reset_token, new_password):
        normalized_email = AuthService._normalize_email(email)
        is_password_valid, password_message = AuthService._validate_password_strength(new_password)
        if not is_password_valid:
            return False, password_message

        is_valid, payload = token_manager.verify_password_reset_token(reset_token or "")
        if not is_valid:
            return False, payload
        if payload.get("email") != normalized_email:
            return False, "Reset token does not match this account."

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (normalized_email,))
            user = cursor.fetchone()
            if not user:
                return False, "Account not found for password reset."

            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (AuthService._hash_password(new_password), user["id"]),
            )
            connection.commit()
            return True, "Password updated successfully. You can now sign in with the new password."
        except Error as exc:
            return False, f"Database error: {exc}"
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def get_dashboard_data(user_id, role):
        if role not in VALID_ROLES:
            return False, "Invalid role.", None

        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            user = AuthService._query_profile(cursor, user_id)
            if not user:
                return False, "User profile not found.", None

            management = None
            notifications = []
            active_loans = []
            if role == "student":
                cursor.execute(
                    """
                    SELECT COUNT(*) AS total_books,
                           COALESCE(SUM(fine_amount), 0) AS total_fines
                    FROM borrow_records
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                summary = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT COUNT(*) AS returned_books
                    FROM transactions t
                    JOIN students s ON s.id = t.student_id
                    WHERE s.user_id = %s
                      AND t.return_date IS NOT NULL
                    """,
                    (user_id,),
                )
                returned_summary = cursor.fetchone() or {}
                cursor.execute(
                    """
                    SELECT COUNT(*) AS active_books
                    FROM transactions t
                    JOIN students s ON s.id = t.student_id
                    WHERE s.user_id = %s
                      AND t.status = 'Issued'
                      AND t.return_date IS NULL
                    """,
                    (user_id,),
                )
                active_summary = cursor.fetchone() or {}
                cursor.execute("SELECT b.title, b.author_name, br.issued_at, br.due_at, br.returned_at, br.fine_amount, br.status FROM borrow_records br JOIN books b ON b.id = br.book_id WHERE br.user_id = %s ORDER BY br.issued_at DESC LIMIT 10", (user_id,))
                activities = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT t.id AS transaction_id,
                           t.book_id,
                           b.title,
                           b.author_name,
                           t.issue_date,
                           t.due_date,
                           t.status
                    FROM transactions t
                    JOIN students s ON s.id = t.student_id
                    JOIN books b ON b.id = t.book_id
                    WHERE s.user_id = %s
                      AND t.status = 'Issued'
                    ORDER BY t.due_date ASC, t.id DESC
                    """,
                    (user_id,),
                )
                loan_rows = cursor.fetchall()
                active_loans = [
                    {
                        "book_id": row["book_id"],
                        "transaction_id": row["transaction_id"],
                        "title": row["title"],
                        "author_name": row["author_name"],
                        "issued_at": row["issue_date"].strftime("%d %b %Y") if row.get("issue_date") else "-",
                        "due_at": row["due_date"].strftime("%d %b %Y") if row.get("due_date") else "-",
                        "status": str(row.get("status") or "Issued").title(),
                        "issued_at_raw": datetime.combine(row["issue_date"], datetime.min.time()) if row.get("issue_date") else None,
                        "due_at_raw": datetime.combine(row["due_date"], datetime.max.time()) if row.get("due_date") else None,
                    }
                    for row in loan_rows
                ]
                notifications = AuthService._build_student_notifications(active_loans)
                for loan in active_loans:
                    loan.pop("issued_at_raw", None)
                    loan.pop("due_at_raw", None)

                stats = [
                    {"label": "Books Issued", "value": int(summary["total_books"] or 0)},
                    {"label": "Currently Active", "value": int(active_summary.get("active_books") or 0)},
                    {"label": "Returned Books", "value": int(returned_summary.get("returned_books") or 0)},
                    {"label": "Total Fine", "value": f"Rs. {AuthService._format_decimal(summary['total_fines']):.2f}"},
                ]
                subheadline = "Students can view their own borrowing history, fines, and personal profile details."
            elif role == "librarian":
                cursor.execute("SELECT COUNT(*) AS total_books FROM books")
                books = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) AS active_members FROM users WHERE role = 'student' AND account_status = 'active'")
                members = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) AS open_issues FROM borrow_records WHERE status IN ('issued', 'overdue')")
                issues = cursor.fetchone()
                cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) AS total_fines FROM borrow_records")
                fines = cursor.fetchone()
                cursor.execute("SELECT b.title, u.full_name AS author_name, br.issued_at, br.due_at, br.returned_at, br.fine_amount, br.status FROM borrow_records br JOIN books b ON b.id = br.book_id JOIN users u ON u.id = br.user_id ORDER BY br.issued_at DESC LIMIT 10")
                activities = cursor.fetchall()
                stats = [
                    {"label": "Catalog Books", "value": int(books["total_books"] or 0)},
                    {"label": "Active Students", "value": int(members["active_members"] or 0)},
                    {"label": "Open Issues", "value": int(issues["open_issues"] or 0)},
                    {"label": "Tracked Fines", "value": f"Rs. {AuthService._format_decimal(fines['total_fines']):.2f}"},
                ]
                subheadline = "Librarians can review activity, monitor students, and maintain their own profile."
            else:
                admin_user_limit = 50
                cursor.execute("SELECT COUNT(*) AS total_users FROM users")
                total_users = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) AS total_books FROM books")
                total_books = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) AS total_transactions FROM borrow_records")
                transactions = cursor.fetchone()
                cursor.execute("SELECT COALESCE(SUM(fine_amount), 0) AS total_fines FROM borrow_records")
                fines = cursor.fetchone()
                cursor.execute("SELECT COUNT(*) AS active_users FROM users WHERE account_status = 'active'")
                active_users = cursor.fetchone()
                cursor.execute("SELECT role, COUNT(*) AS total FROM users GROUP BY role")
                role_rows = cursor.fetchall()
                role_totals = {item["role"]: int(item["total"] or 0) for item in role_rows}
                cursor.execute(
                    "SELECT u.id, u.full_name, u.email, u.role, u.account_status, p.membership_code, p.department, p.joined_on, u.last_login "
                    "FROM users u "
                    "JOIN user_profiles p ON p.user_id = u.id "
                    "ORDER BY FIELD(u.role, 'admin', 'librarian', 'student'), u.created_at ASC "
                    "LIMIT %s",
                    (admin_user_limit,),
                )
                managed_users = cursor.fetchall()
                cursor.execute(
                    "SELECT b.title, u.full_name AS author_name, br.issued_at, br.due_at, br.returned_at, br.fine_amount, br.status "
                    "FROM borrow_records br "
                    "JOIN books b ON b.id = br.book_id "
                    "JOIN users u ON u.id = br.user_id "
                    "ORDER BY br.issued_at DESC "
                    "LIMIT 30"
                )
                activities = cursor.fetchall()
                total_user_count = int(total_users["total_users"] or 0)
                stats = [
                    {"label": "All Users", "value": total_user_count},
                    {"label": "Books", "value": int(total_books["total_books"] or 0)},
                    {"label": "Transactions", "value": int(transactions["total_transactions"] or 0)},
                    {"label": "Total Fines", "value": f"Rs. {AuthService._format_decimal(fines['total_fines']):.2f}"},
                ]
                subheadline = "Admins can monitor users and all issue, due, return, and fine records."
                management = {
                    "headline": "Registered Users",
                    "summary": [
                        {"label": "Active Users", "value": int(active_users["active_users"] or 0)},
                        {"label": "Students", "value": role_totals.get("student", 0)},
                        {"label": "Librarians", "value": role_totals.get("librarian", 0)},
                        {"label": "Admins", "value": role_totals.get("admin", 0)},
                    ],
                    "total_users": total_user_count,
                    "displayed_users": len(managed_users),
                    "is_truncated": total_user_count > len(managed_users),
                    "users": [
                        {
                            "id": item["id"],
                            "full_name": item["full_name"],
                            "email": item["email"],
                            "role": item["role"].title(),
                            "status": item["account_status"].title(),
                            "membership_code": item["membership_code"],
                            "department": item["department"],
                            "joined_on": item["joined_on"].strftime("%d %b %Y") if item.get("joined_on") else "-",
                            "last_login": item["last_login"].strftime("%d %b %Y, %I:%M %p") if item.get("last_login") else "Never",
                        }
                        for item in managed_users
                    ],
                }

            activity_rows = []
            for item in activities:
                fine_value = item.get("fine_amount", 0)
                activity_rows.append({
                    "title": item.get("title"),
                    "author": item.get("author_name", "-"),
                    "issued_at": item["issued_at"].strftime("%d %b %Y, %I:%M %p") if item.get("issued_at") else "-",
                    "due_at": item["due_at"].strftime("%d %b %Y, %I:%M %p") if item.get("due_at") else "-",
                    "returned_at": item["returned_at"].strftime("%d %b %Y, %I:%M %p") if item.get("returned_at") else "-",
                    "fine_amount": f"Rs. {AuthService._format_decimal(fine_value):.2f}",
                    "status": str(item.get("status", "active")).title(),
                })

            profile = {
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"].title(),
                "profession_title": user["profession_title"],
                "membership_code": user["membership_code"],
                "department": user["department"],
                "bio": user["bio"] or "Add a short bio from the profile editor.",
                "profile_image_url": user["profile_image_url"] or "",
                "joined_on": user["joined_on"].strftime("%d %b %Y") if user["joined_on"] else "-",
                "last_login": user["last_login"].strftime("%d %b %Y, %I:%M %p") if user["last_login"] else "First login",
                "initials": "".join(part[0].upper() for part in user["full_name"].split()[:2]),
                "avatar_color": user["avatar_color"],
                "can_manage_records": role == "admin",
                "can_edit_profile": True,
            }
            dashboard = {
                "headline": f"{role.title()} Dashboard",
                "subheadline": subheadline,
                "stats": stats,
                "activities": activity_rows,
                "show_activity": True,
                "notifications": notifications,
                "active_loans": active_loans,
            }
            return True, "Dashboard data loaded successfully.", {"profile": profile, "dashboard": dashboard, "management": management}
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def get_profile(user_id):
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            user = AuthService._query_profile(cursor, user_id)
            if not user:
                return False, "User profile not found.", None
            return True, "Profile loaded successfully.", {
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"].title(),
                "profession_title": user["profession_title"],
                "membership_code": user["membership_code"],
                "department": user["department"],
                "bio": user["bio"] or "",
                "profile_image_url": user["profile_image_url"] or "",
                "joined_on": user["joined_on"].strftime("%d %b %Y") if user["joined_on"] else "-",
                "last_login": user["last_login"].strftime("%d %b %Y, %I:%M %p") if user["last_login"] else "First login",
            }
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def update_profile(user_id, bio, profile_image_url):
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "UPDATE user_profiles SET bio = %s, profile_image_url = %s WHERE user_id = %s",
                ((bio or "").strip()[:500], (profile_image_url or "").strip()[:255], user_id),
            )
            connection.commit()
            cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            user = cursor.fetchone()
            return AuthService.get_dashboard_data(user_id, user["role"])
        except Error as exc:
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
