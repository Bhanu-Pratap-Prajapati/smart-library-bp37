import site
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
for extra_path in (BASE_DIR / '_vendor', Path(site.getusersitepackages())):
    path_str = str(extra_path)
    try:
        should_add = extra_path.exists() and path_str not in sys.path
    except OSError:
        should_add = False
    if should_add:
        sys.path.insert(0, path_str)

from dotenv import load_dotenv
from mysql.connector import Error, connect

from config import config
from services.book_service import BookService
from services.auth_service import AuthService, DEMO_USERS, ROLE_TITLES


load_dotenv(BASE_DIR / ".env")
SCHEMA_FILE = BASE_DIR.parent / "database" / "schema.sql"
IGNORED_SCHEMA_ERROR_CODES = {1050, 1060, 1061, 1072}


def upsert_student_record(cursor, user_id, name, email):
    cursor.execute(
        "SELECT id FROM students WHERE email = %s",
        (email,),
    )
    existing_student = cursor.fetchone()
    if existing_student:
        cursor.execute(
            "UPDATE students SET user_id = %s, name = %s WHERE id = %s",
            (user_id, name, existing_student[0]),
        )
        return

    cursor.execute(
        "INSERT INTO students (user_id, name, email) VALUES (%s, %s, %s)",
        (user_id, name, email),
    )


def ensure_primary_admin(cursor):
    name = (config.primary_admin_name or "").strip()
    email = (config.primary_admin_email or "").strip().lower()
    password = config.primary_admin_password or ""
    if not (name and email and password):
        return

    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    email_match = cursor.fetchone()
    if email_match:
        cursor.execute(
            "UPDATE users SET full_name = %s, password_hash = %s, role = 'admin', account_status = 'active' WHERE id = %s",
            (name, AuthService._hash_password(password), email_match[0]),
        )
        user_id = email_match[0]
    else:
        cursor.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1")
        existing_admin = cursor.fetchone()
        if existing_admin:
            user_id = existing_admin[0]
            cursor.execute(
                "UPDATE users SET full_name = %s, email = %s, password_hash = %s, role = 'admin', account_status = 'active' WHERE id = %s",
                (name, email, AuthService._hash_password(password), user_id),
            )
        else:
            cursor.execute(
                "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, 'admin')",
                (name, email, AuthService._hash_password(password)),
            )
            user_id = cursor.lastrowid

    cursor.execute("SELECT user_id FROM user_profiles WHERE user_id = %s", (user_id,))
    profile = cursor.fetchone()
    if profile:
        cursor.execute(
            "UPDATE user_profiles SET membership_code = %s, profession_title = %s, department = %s, bio = %s, profile_image_url = %s, joined_on = COALESCE(joined_on, CURDATE()), avatar_color = %s WHERE user_id = %s",
            (
                f"ADM-{str(user_id).zfill(5)}",
                ROLE_TITLES["admin"],
                "Administration",
                "Primary admin account created through protected setup.",
                "",
                "#ef4444",
                user_id,
            ),
        )
    else:
        cursor.execute(
            "INSERT INTO user_profiles (user_id, membership_code, profession_title, department, bio, profile_image_url, joined_on, avatar_color) VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s)",
            (
                user_id,
                f"ADM-{str(user_id).zfill(5)}",
                ROLE_TITLES["admin"],
                "Administration",
                "Primary admin account created through protected setup.",
                "",
                "#ef4444",
            ),
        )


def seed_demo_users(cursor):
    for demo_user in DEMO_USERS:
        cursor.execute("SELECT id FROM users WHERE email = %s", (demo_user["email"].lower(),))
        existing_user = cursor.fetchone()
        if existing_user:
            if demo_user["role"] == "student":
                upsert_student_record(cursor, existing_user[0], demo_user["full_name"], demo_user["email"].lower())
            continue

        cursor.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (
                demo_user["full_name"],
                demo_user["email"].lower(),
                AuthService._hash_password(demo_user["password"]),
                demo_user["role"],
            ),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO user_profiles (user_id, membership_code, profession_title, department, bio, profile_image_url, joined_on, avatar_color) VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s)",
            (
                user_id,
                f"{demo_user['role'][:3].upper()}-{str(user_id).zfill(5)}",
                ROLE_TITLES[demo_user["role"]],
                demo_user["department"],
                demo_user["bio"],
                "",
                demo_user["avatar_color"],
            ),
        )
        if demo_user["role"] == "student":
            upsert_student_record(cursor, user_id, demo_user["full_name"], demo_user["email"].lower())


def main():
    connection = connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
    )
    cursor = connection.cursor()

    with open(SCHEMA_FILE, "r", encoding="utf-8") as schema_file:
        sql_commands = schema_file.read()

    for statement in [item.strip() for item in sql_commands.split(";") if item.strip()]:
        try:
            cursor.execute(statement)
        except Error as exc:
            if getattr(exc, "errno", None) not in IGNORED_SCHEMA_ERROR_CODES:
                raise

    connection.commit()
    BookService.ensure_library_schema()

    ensure_primary_admin(cursor)
    seed_demo_users(cursor)
    connection.commit()
    cursor.close()
    connection.close()
    print("Database schema initialized successfully with protected admin setup and demo users.")


if __name__ == "__main__":
    main()





