import json
from difflib import SequenceMatcher
from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode
from urllib.request import urlopen

from mysql.connector import Error

from db import db


class BookService:
    GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
    SUBJECT_QUERIES = [
        "artificial intelligence",
        "machine learning",
        "data science",
        "economics",
        "history",
        "software engineering",
        "psychology",
        "self improvement",
    ]
    MAX_BOOKS = 48
    BOOKS_PER_SUBJECT = 10
    MIN_PERSISTED_BOOKS = 40
    FINE_PER_DAY = 10
    DEFAULT_ISSUE_DAYS = 3
    FALLBACK_BOOKS = [
        {"book_code": "BK-LOCAL-001", "title": "Introduction to Artificial Intelligence", "author_name": "Stuart Russell", "category": "Artificial Intelligence", "description": "Core foundations of AI systems and intelligent agents.", "published_date": "2022"},
        {"book_code": "BK-LOCAL-002", "title": "Hands-On Machine Learning", "author_name": "Aurelien Geron", "category": "Machine Learning", "description": "Practical machine learning workflows with real examples.", "published_date": "2023"},
        {"book_code": "BK-LOCAL-003", "title": "Principles of Data Science", "author_name": "Sinan Ozdemir", "category": "Data Science", "description": "Data-driven thinking, analytics, and deployment basics.", "published_date": "2021"},
        {"book_code": "BK-LOCAL-004", "title": "Data Visualization Essentials", "author_name": "Cole Nussbaumer Knaflic", "category": "Data Science", "description": "Clear storytelling with charts and visual communication.", "published_date": "2020"},
        {"book_code": "BK-LOCAL-005", "title": "Modern Microeconomics", "author_name": "Robert Pindyck", "category": "Economics", "description": "Microeconomic principles, models, and applied interpretation.", "published_date": "2022"},
        {"book_code": "BK-LOCAL-006", "title": "Macroeconomics in Practice", "author_name": "N. Gregory Mankiw", "category": "Economics", "description": "Macroeconomic indicators, policy, and growth concepts.", "published_date": "2021"},
        {"book_code": "BK-LOCAL-007", "title": "World History: A Concise Study", "author_name": "Norman Lowe", "category": "History", "description": "Major global historical events in concise chapters.", "published_date": "2019"},
        {"book_code": "BK-LOCAL-008", "title": "India Through the Ages", "author_name": "Romila Thapar", "category": "History", "description": "A readable narrative of India's social and political history.", "published_date": "2018"},
        {"book_code": "BK-LOCAL-009", "title": "Clean Code Practices", "author_name": "Robert Martin", "category": "Software Engineering", "description": "Writing maintainable and readable software in teams.", "published_date": "2017"},
        {"book_code": "BK-LOCAL-010", "title": "Atomic Habits", "author_name": "James Clear", "category": "Self Improvement", "description": "Proven methods to build useful habits and routines.", "published_date": "2018"},
        {"book_code": "BK-LOCAL-011", "title": "Deep Work", "author_name": "Cal Newport", "category": "Productivity", "description": "Focus strategies for knowledge workers and students.", "published_date": "2016"},
        {"book_code": "BK-LOCAL-012", "title": "Thinking, Fast and Slow", "author_name": "Daniel Kahneman", "category": "Psychology", "description": "How cognitive systems shape decisions and behavior.", "published_date": "2011"},
    ]

    @staticmethod
    def _inventory_status(available_copies):
        return "Available" if int(available_copies or 0) > 0 else "Issued"

    @staticmethod
    def _fallback_catalog():
        catalog = []
        seeds = list(BookService.FALLBACK_BOOKS)
        generated_idx = 1
        variants = [
            ("Artificial Intelligence", "Smart AI Concepts", "A practical understanding of intelligent systems."),
            ("Machine Learning", "Applied ML Notebook", "Essential machine learning workflows and practice sets."),
            ("Data Science", "Data Science Toolkit", "Data wrangling, models, and result interpretation."),
            ("Economics", "Economic Thinking", "Micro and macro economics with practical examples."),
            ("History", "History in Context", "Events and timelines with short, high-value summaries."),
            ("Software Engineering", "Reliable Systems", "System design and maintainable architecture basics."),
            ("Psychology", "Human Behavior Essentials", "Core psychology concepts for modern learners."),
            ("Self Improvement", "Better Daily Habits", "Simple methods for effective routines and growth."),
        ]
        while len(seeds) < BookService.MIN_PERSISTED_BOOKS + 8:
            topic, title_seed, desc_seed = variants[(generated_idx - 1) % len(variants)]
            seeds.append(
                {
                    "book_code": f"BK-LOCAL-{200 + generated_idx:03d}",
                    "title": f"{title_seed} Vol {generated_idx}",
                    "author_name": f"Smart Library Author {generated_idx}",
                    "category": topic,
                    "description": desc_seed,
                    "published_date": str(2010 + (generated_idx % 15)),
                }
            )
            generated_idx += 1

        for item in seeds:
            catalog.append({
                "google_book_id": f"local-{item['book_code'].lower()}",
                "book_code": item["book_code"],
                "title": item["title"],
                "author_name": item["author_name"],
                "isbn": None,
                "thumbnail_url": "",
                "category": item["category"],
                "description": item["description"],
                "cover_url": "",
                "published_date": item["published_date"],
                "total_copies": 5,
                "available_copies": 5,
                "status": "Available",
            })
        return catalog

    @staticmethod
    def _fallback_search(query_text):
        words = [word for word in (query_text or "").strip().lower().split() if word]
        if not words:
            return []
        matches = []
        for book in BookService._fallback_catalog():
            haystack = " ".join([book["title"], book["author_name"], book["category"], book["description"]]).lower()
            if all(word in haystack for word in words):
                matches.append(book)
        return matches[:10]

    @staticmethod
    def _normalized_text(value):
        return str(value or "").strip().lower()

    @staticmethod
    def _split_query_tokens(query_text):
        return [token for token in BookService._normalized_text(query_text).split() if token]

    @staticmethod
    def _rank_book_match(book, query_text):
        query = BookService._normalized_text(query_text)
        if not query:
            return None

        book_id_text = str(book.get("id") or "").strip().lower()
        search_fields = [
            BookService._normalized_text(book.get("title")),
            BookService._normalized_text(book.get("author_name")),
            BookService._normalized_text(book.get("book_code")),
            BookService._normalized_text(book.get("isbn")),
            book_id_text,
        ]
        search_fields = [field for field in search_fields if field]
        if not search_fields:
            return None

        if query in search_fields:
            id_bonus = 0.2 if query == book_id_text else 0.0
            return 0, 1.2 + id_bonus

        starts_with = any(field.startswith(query) for field in search_fields)
        contains = any(query in field for field in search_fields)
        if contains:
            token_bonus = 0.0
            for token in BookService._split_query_tokens(query):
                if any(token and token in field for field in search_fields):
                    token_bonus += 0.03
            partial_score = 1.0 + (0.15 if starts_with else 0.0) + min(token_bonus, 0.15)
            return 1, partial_score

        fuzzy_score = max(SequenceMatcher(None, query, field).ratio() for field in search_fields)
        for token in BookService._split_query_tokens(query):
            token_score = max(SequenceMatcher(None, token, field).ratio() for field in search_fields)
            fuzzy_score = max(fuzzy_score, token_score)

        if fuzzy_score >= 0.72:
            return 2, fuzzy_score
        return None

    @staticmethod
    def ensure_library_schema():
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS books (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    book_code VARCHAR(40) NOT NULL UNIQUE,
                    google_book_id VARCHAR(100) NULL UNIQUE,
                    title VARCHAR(255) NOT NULL,
                    author_name VARCHAR(255) NOT NULL,
                    category VARCHAR(150) NOT NULL,
                    description TEXT NULL,
                    cover_url TEXT NULL,
                    published_date VARCHAR(50) NULL,
                    total_copies INT NOT NULL DEFAULT 5,
                    available_copies INT NOT NULL DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for statement in [
                "ALTER TABLE books ADD COLUMN isbn VARCHAR(32) NULL",
                "ALTER TABLE books ADD COLUMN thumbnail_url TEXT NULL",
                "ALTER TABLE books ADD COLUMN total_copies INT NOT NULL DEFAULT 5",
                "ALTER TABLE books ADD COLUMN status ENUM('Available', 'Issued') NOT NULL DEFAULT 'Available'",
            ]:
                try:
                    cursor.execute(statement)
                except Error as exc:
                    if getattr(exc, "errno", None) != 1060:
                        raise
            cursor.execute("UPDATE books SET total_copies = available_copies WHERE total_copies < available_copies")
            cursor.execute("UPDATE books SET status = CASE WHEN available_copies > 0 THEN 'Available' ELSE 'Issued' END")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS students (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(120) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            for statement in [
                "ALTER TABLE students ADD COLUMN user_id INT NULL UNIQUE",
                "ALTER TABLE students ADD CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL",
            ]:
                try:
                    cursor.execute(statement)
                except Error as exc:
                    if getattr(exc, "errno", None) not in {1060, 1061, 1826}:
                        raise

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    status ENUM('Issued', 'Returned', 'Overdue') NOT NULL DEFAULT 'Issued',
                    book_id INT NOT NULL,
                    student_id INT NOT NULL,
                    issue_date DATE NOT NULL,
                    return_date DATE NULL,
                    due_date DATE NOT NULL,
                    fine_amount DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                    fine_per_day DECIMAL(10, 2) NOT NULL DEFAULT 10.00,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
                )
                """
            )
            for statement in [
                "CREATE INDEX idx_books_status ON books(status)",
                "CREATE INDEX idx_students_user ON students(user_id)",
                "CREATE INDEX idx_transactions_book_status ON transactions(book_id, status)",
                "CREATE INDEX idx_transactions_student_status ON transactions(student_id, status)",
            ]:
                try:
                    cursor.execute(statement)
                except Error as exc:
                    if getattr(exc, "errno", None) != 1061:
                        raise

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS fine_payments (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    transaction_id INT NOT NULL,
                    paid_by_user_id INT NOT NULL,
                    amount DECIMAL(10, 2) NOT NULL,
                    payment_reference VARCHAR(64) NOT NULL UNIQUE,
                    payment_mode VARCHAR(30) NOT NULL DEFAULT 'simulation',
                    payment_status ENUM('paid') NOT NULL DEFAULT 'paid',
                    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                    FOREIGN KEY (paid_by_user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            try:
                cursor.execute("CREATE INDEX idx_fine_payments_transaction ON fine_payments(transaction_id)")
            except Error as exc:
                if getattr(exc, "errno", None) != 1061:
                    raise

            connection.commit()
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def ensure_books_schema():
        BookService.ensure_library_schema()

    @staticmethod
    def _normalize_book(item):
        info = item.get("volumeInfo", {})
        authors = info.get("authors") or ["Unknown Author"]
        categories = info.get("categories") or ["General"]
        image_links = info.get("imageLinks") or {}
        identifiers = info.get("industryIdentifiers") or []

        isbn = None
        for identifier in identifiers:
            if identifier.get("type") in {"ISBN_13", "ISBN_10"}:
                candidate = (identifier.get("identifier") or "").strip()[:32]
                if candidate:
                    isbn = candidate
                    break

        google_book_id = (item.get("id") or "").strip()
        if not google_book_id:
            return None

        thumbnail = (image_links.get("thumbnail") or image_links.get("smallThumbnail") or "").replace("http://", "https://")
        return {
            "google_book_id": google_book_id,
            "book_code": f"BK-{google_book_id[:10].upper()}",
            "title": (info.get("title") or "Untitled Book")[:255],
            "author_name": ", ".join(authors)[:255],
            "isbn": isbn,
            "thumbnail_url": thumbnail,
            "category": ", ".join(categories)[:150],
            "description": (info.get("description") or "No description available.")[:4000],
            "cover_url": thumbnail,
            "published_date": (info.get("publishedDate") or "")[:50],
            "total_copies": 5,
            "available_copies": 5,
            "status": "Available",
        }

    @staticmethod
    def _parse_date(value, field_name):
        if isinstance(value, date):
            return value
        if not value:
            raise ValueError(f"{field_name} is required.")
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc

    @staticmethod
    def _calculate_fine(current_date, due_date, fine_per_day=10):
        days_diff = max((current_date - due_date).days, 0)
        return days_diff, float(days_diff * fine_per_day)

    @staticmethod
    def _day_start(value):
        return datetime.combine(value, time.min)

    @staticmethod
    def _day_end(value):
        return datetime.combine(value, time.max.replace(microsecond=0))

    @staticmethod
    def fetch_books_from_google():
        seen_ids = set()
        books = []

        for query in BookService.SUBJECT_QUERIES:
            params = urlencode({
                "q": query,
                "maxResults": BookService.BOOKS_PER_SUBJECT,
                "printType": "books",
                "langRestrict": "en",
                "orderBy": "relevance",
            })
            with urlopen(f"{BookService.GOOGLE_BOOKS_URL}?{params}", timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))

            for item in payload.get("items", []):
                book = BookService._normalize_book(item)
                if not book or book["google_book_id"] in seen_ids:
                    continue
                books.append(book)
                seen_ids.add(book["google_book_id"])
                if len(books) >= BookService.MAX_BOOKS:
                    return books

        return books[:BookService.MAX_BOOKS]

    @staticmethod
    def search_google_books(query_text, max_results=10):
        params = urlencode({
            "q": query_text,
            "maxResults": max_results,
            "printType": "books",
            "orderBy": "relevance",
        })
        with urlopen(f"{BookService.GOOGLE_BOOKS_URL}?{params}", timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return [book for item in payload.get("items", []) if (book := BookService._normalize_book(item))]

    @staticmethod
    def save_books(books):
        connection = None
        cursor = None
        saved_books = []
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            query = """
                INSERT INTO books (
                    book_code, google_book_id, title, author_name, isbn, thumbnail_url, category,
                    description, cover_url, published_date, total_copies, available_copies, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    author_name = VALUES(author_name),
                    isbn = COALESCE(VALUES(isbn), isbn),
                    thumbnail_url = VALUES(thumbnail_url),
                    category = VALUES(category),
                    description = VALUES(description),
                    cover_url = VALUES(cover_url),
                    published_date = VALUES(published_date)
            """
            for book in books:
                cursor.execute(
                    query,
                    (
                        book["book_code"],
                        book["google_book_id"],
                        book["title"],
                        book["author_name"],
                        book["isbn"],
                        book["thumbnail_url"],
                        book["category"],
                        book["description"],
                        book["cover_url"],
                        book["published_date"],
                        book["total_copies"],
                        book["available_copies"],
                        book["status"],
                    ),
                )
                cursor.execute(
                    """
                    SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                           category, description, cover_url, published_date, total_copies, available_copies, status
                    FROM books
                    WHERE google_book_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (book["google_book_id"],),
                )
                row = cursor.fetchone()
                if row:
                    saved_books.append(row)
            connection.commit()
            return saved_books
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def load_saved_books(limit=48):
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                       category, description, cover_url, published_date, total_copies, available_copies, status
                FROM books
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def search_saved_books(query_text, limit=15):
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cleaned_query = (query_text or "").strip()
            if not cleaned_query:
                return []
            cursor.execute(
                """
                SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                       category, description, cover_url, published_date, total_copies, available_copies, status
                FROM books
                ORDER BY id DESC
                """,
            )
            rows = cursor.fetchall()

            ranked = []
            for row in rows:
                match_rank = BookService._rank_book_match(row, cleaned_query)
                if not match_rank:
                    continue
                rank_bucket, rank_score = match_rank
                ranked.append((rank_bucket, rank_score, row))

            ranked.sort(
                key=lambda item: (
                    item[0],
                    -item[1],
                    -int(item[2].get("available_copies") or 0),
                    -int(item[2].get("id") or 0),
                )
            )
            return [item[2] for item in ranked[:limit]]
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def _books_count():
        connection = None
        cursor = None
        try:
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT COUNT(*) AS total FROM books")
            row = cursor.fetchone()
            return int((row or {}).get("total") or 0)
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def get_books(refresh=False):
        try:
            BookService.ensure_library_schema()
            saved_books = BookService.load_saved_books(limit=BookService.MAX_BOOKS)
            total_books = BookService._books_count()
            needs_minimum_seed = total_books < BookService.MIN_PERSISTED_BOOKS

            # DB-first strategy: return existing persistent data unless refresh is requested
            if saved_books and not refresh and not needs_minimum_seed:
                return True, "Books loaded successfully from MySQL.", saved_books

            if refresh or not saved_books or needs_minimum_seed:
                api_error = None
                try:
                    fresh_books = BookService.fetch_books_from_google()
                except Exception as exc:
                    fresh_books = []
                    api_error = exc

                if fresh_books:
                    BookService.save_books(fresh_books)
                    saved_books = BookService.load_saved_books(limit=BookService.MAX_BOOKS)
                    source_message = "Books refreshed successfully from Google Books API."
                elif needs_minimum_seed or not saved_books:
                    BookService.save_books(BookService._fallback_catalog())
                    saved_books = BookService.load_saved_books(limit=BookService.MAX_BOOKS)
                    source_message = "Google Books unavailable. Loaded local fallback catalog into MySQL."
                else:
                    source_message = "No books returned by Google Books API."
                    if api_error:
                        source_message = f"{source_message} ({api_error})"
            else:
                source_message = "Books loaded successfully from MySQL."

            return True, source_message, saved_books
        except Error as exc:
            return False, f"Database error: {exc}", []
        except Exception as exc:
            return False, f"Unable to load books: {exc}", []

    @staticmethod
    def search_and_store_book(query_text):
        if not (query_text or "").strip():
            raise ValueError("query is required.")

        BookService.ensure_library_schema()
        cleaned_query = query_text.strip()

        # First check DB for permanent records
        existing_books = BookService.search_saved_books(cleaned_query, limit=15)
        if existing_books:
            return True, "Books loaded from MySQL for this search.", existing_books

        # Not found in DB, fetch from API and persist
        try:
            books = BookService.search_google_books(cleaned_query, max_results=10)
        except Exception:
            books = BookService._fallback_search(cleaned_query)

        if not books:
            return True, "No books found for the given search.", []

        BookService.save_books(books)
        ranked_books = BookService.search_saved_books(cleaned_query, limit=15)
        return True, "Books fetched from external/local source, stored in MySQL, and returned successfully.", ranked_books

    @staticmethod
    def get_search_suggestions(query_text, limit=5):
        cleaned_query = (query_text or "").strip()
        if len(cleaned_query) < 1:
            return True, "Type to get suggestions.", []

        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, title, author_name, book_code, isbn
                FROM books
                ORDER BY id DESC
                """,
            )
            rows = cursor.fetchall()

            ranked_titles = []
            for row in rows:
                match_rank = BookService._rank_book_match(row, cleaned_query)
                if not match_rank:
                    continue
                rank_bucket, rank_score = match_rank
                ranked_titles.append((rank_bucket, rank_score, str(row.get("title") or "").strip()))

            ranked_titles.sort(key=lambda item: (item[0], -item[1], item[2].lower()))

            suggestions = []
            seen = set()
            for _, _, title in ranked_titles:
                key = title.lower()
                if not title or key in seen:
                    continue
                seen.add(key)
                suggestions.append({"type": "title", "value": title})
                if len(suggestions) >= limit:
                    break
            return True, "Suggestions loaded successfully.", suggestions
        except Error as exc:
            return False, f"Database error: {exc}", []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def get_recommendations(query_text=None, limit=8):
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cleaned_query = (query_text or "").strip()
            if cleaned_query:
                wildcard = f"%{cleaned_query}%"
                cursor.execute(
                    """
                    SELECT category, author_name
                    FROM books
                    WHERE title LIKE %s OR author_name LIKE %s OR book_code LIKE %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (wildcard, wildcard, wildcard),
                )
                matched = cursor.fetchone()
            else:
                matched = None

            if matched:
                category = matched.get("category") or ""
                author_name = matched.get("author_name") or ""
                cursor.execute(
                    """
                    SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                           category, description, cover_url, published_date, total_copies, available_copies, status
                    FROM books
                    WHERE category = %s OR author_name = %s
                    ORDER BY available_copies DESC, created_at DESC
                    LIMIT %s
                    """,
                    (category, author_name, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                           category, description, cover_url, published_date, total_copies, available_copies, status
                    FROM books
                    ORDER BY available_copies DESC, created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
            return True, "Recommendations loaded successfully.", cursor.fetchall()
        except Error as exc:
            return False, f"Database error: {exc}", []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def add_book(
        title,
        author_name,
        category="General",
        total_copies=5,
        description="",
        published_date="",
        isbn=None,
        cover_url="",
    ):
        cleaned_title = (title or "").strip()
        cleaned_author = (author_name or "").strip()
        if len(cleaned_title) < 2:
            return False, "title is required.", None
        if len(cleaned_author) < 2:
            return False, "author_name is required.", None

        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            safe_copies = max(int(total_copies or 1), 1)
            book_code = f"BK-MANUAL-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[-12:]}"
            cursor.execute(
                """
                INSERT INTO books (
                    book_code, google_book_id, title, author_name, isbn, thumbnail_url, category,
                    description, cover_url, published_date, total_copies, available_copies, status
                ) VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Available')
                """,
                (
                    book_code,
                    cleaned_title[:255],
                    cleaned_author[:255],
                    (isbn or "").strip()[:32] or None,
                    (cover_url or "").strip(),
                    (category or "General").strip()[:150],
                    (description or "").strip()[:4000],
                    (cover_url or "").strip(),
                    (published_date or "").strip()[:50],
                    safe_copies,
                    safe_copies,
                ),
            )
            connection.commit()
            cursor.execute(
                """
                SELECT id, book_code, google_book_id, title, author_name, isbn, thumbnail_url,
                       category, description, cover_url, published_date, total_copies, available_copies, status
                FROM books
                WHERE id = %s
                """,
                (cursor.lastrowid,),
            )
            return True, "Book added successfully.", cursor.fetchone()
        except Error as exc:
            if connection:
                connection.rollback()
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def remove_book(book_id):
        if not book_id:
            return False, "book_id is required.", None
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT id, title FROM books WHERE id = %s", (book_id,))
            book = cursor.fetchone()
            if not book:
                return False, "Book not found.", None
            cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))
            connection.commit()
            return True, "Book removed successfully.", {"book_id": book_id, "title": book["title"]}
        except Error as exc:
            if connection:
                connection.rollback()
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def create_student(name, email, user_id=None):
        if len((name or "").strip()) < 3:
            return False, "Student name must be at least 3 characters long.", None
        email = (email or "").strip().lower()
        if not email:
            return False, "Student email is required.", None

        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            if user_id:
                cursor.execute("SELECT id, full_name, email, role FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                if not user:
                    return False, "Linked user not found.", None
                if user["role"] != "student":
                    return False, "Only student users can be linked to student records.", None
                email = user["email"]
                name = user["full_name"]

            cursor.execute("SELECT id, user_id, name, email FROM students WHERE email = %s", (email,))
            existing = cursor.fetchone()
            if existing:
                if user_id and existing.get("user_id") != user_id:
                    cursor.execute("UPDATE students SET user_id = %s, name = %s WHERE id = %s", (user_id, name, existing["id"]))
                    connection.commit()
                    existing["user_id"] = user_id
                    existing["name"] = name
                return True, "Student already exists.", existing

            cursor.execute(
                "INSERT INTO students (user_id, name, email) VALUES (%s, %s, %s)",
                (user_id, name.strip(), email),
            )
            student_id = cursor.lastrowid
            connection.commit()
            return True, "Student created successfully.", {
                "id": student_id,
                "user_id": user_id,
                "name": name.strip(),
                "email": email,
            }
        except Error as exc:
            if connection:
                connection.rollback()
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def sync_student_from_user(user_id, name, email):
        return BookService.create_student(name=name, email=email, user_id=user_id)

    @staticmethod
    def list_students():
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT s.id, s.user_id, s.name, s.email, s.created_at,
                       u.account_status, u.last_login
                FROM students s
                LEFT JOIN users u ON u.id = s.user_id
                ORDER BY s.name ASC
                """
            )
            rows = cursor.fetchall()
            return True, "Students loaded successfully.", rows
        except Error as exc:
            return False, f"Database error: {exc}", []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def issue_book(
        book_id,
        student_id,
        issue_date=None,
        due_date=None,
        issued_by=None,
        issuer_user_id=None,
        issuer_role=None,
    ):
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            if not book_id:
                raise ValueError("book_id is required.")

            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            role = (issuer_role or "").strip().lower()
            if role == "student":
                if not issuer_user_id:
                    raise ValueError("Authenticated user is required for student issue.")
                cursor.execute(
                    "SELECT id, user_id, name, email FROM students WHERE user_id = %s",
                    (issuer_user_id,),
                )
                student = cursor.fetchone()
                if not student:
                    raise ValueError("Student profile is not linked with this account.")
                student_id = student["id"]
            else:
                if not student_id:
                    raise ValueError("student_id is required.")
                cursor.execute("SELECT id, user_id, name, email FROM students WHERE id = %s", (student_id,))
                student = cursor.fetchone()
                if not student:
                    raise ValueError("Student not found.")

            cursor.execute("SELECT id, title, status, available_copies, total_copies FROM books WHERE id = %s", (book_id,))
            book = cursor.fetchone()
            if not book:
                raise ValueError("Book not found.")
            if int(book.get("available_copies") or 0) <= 0:
                raise ValueError("No available copies left for this book.")

            issue_datetime = datetime.now()
            issue_date_value = issue_datetime.date()
            due_date_value = issue_date_value + timedelta(days=BookService.DEFAULT_ISSUE_DAYS)
            if due_date_value < issue_date_value:
                raise ValueError("due_date must be on or after issue_date.")

            cursor.execute(
                """
                INSERT INTO transactions (status, book_id, student_id, issue_date, due_date, fine_per_day)
                VALUES ('Issued', %s, %s, %s, %s, %s)
                """,
                (book_id, student_id, issue_date_value, due_date_value, BookService.FINE_PER_DAY),
            )
            transaction_id = cursor.lastrowid

            if student.get("user_id"):
                effective_issued_by = issued_by or issuer_user_id
                cursor.execute(
                    """
                    INSERT INTO borrow_records (user_id, book_id, issued_by, issued_at, due_at, status)
                    VALUES (%s, %s, %s, %s, %s, 'issued')
                    """,
                    (
                        student["user_id"],
                        book_id,
                        effective_issued_by,
                        BookService._day_start(issue_date_value),
                        BookService._day_end(due_date_value),
                    ),
                )

            next_available_copies = int(book["available_copies"]) - 1
            next_status = BookService._inventory_status(next_available_copies)
            cursor.execute(
                "UPDATE books SET available_copies = %s, status = %s WHERE id = %s",
                (next_available_copies, next_status, book_id),
            )
            connection.commit()

            return True, "Book issued successfully.", {
                "transaction_id": transaction_id,
                "book_id": book_id,
                "student_id": student_id,
                "student_name": student["name"],
                "issue_date": issue_date_value.isoformat(),
                "due_date": due_date_value.isoformat(),
                "status": next_status,
                "available_copies": next_available_copies,
                "total_copies": int(book["total_copies"] or next_available_copies + 1),
            }
        except (Error, ValueError) as exc:
            if connection:
                connection.rollback()
            return False, str(exc), None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def list_my_issued_books(user_id, role):
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            role = (role or "").strip().lower()
            if role == "student":
                cursor.execute(
                    """
                    SELECT t.id AS transaction_id, t.book_id, t.issue_date, t.due_date, t.status,
                           b.title, b.author_name
                    FROM transactions t
                    INNER JOIN students s ON s.id = t.student_id
                    INNER JOIN books b ON b.id = t.book_id
                    WHERE s.user_id = %s
                      AND t.status = 'Issued'
                    ORDER BY t.issue_date DESC, t.id DESC
                    """,
                    (user_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT t.id AS transaction_id, t.book_id, t.issue_date, t.due_date, t.status,
                           b.title, b.author_name, u.full_name AS borrowed_by
                    FROM transactions t
                    INNER JOIN students s ON s.id = t.student_id
                    INNER JOIN users u ON u.id = s.user_id
                    INNER JOIN books b ON b.id = t.book_id
                    WHERE t.status = 'Issued'
                    ORDER BY t.issue_date DESC, t.id DESC
                    """,
                )

            rows = cursor.fetchall()
            response = []
            for row in rows:
                item = {
                    "transaction_id": row["transaction_id"],
                    "book_id": row["book_id"],
                    "title": row["title"],
                    "author_name": row["author_name"],
                    "issued_at": row["issue_date"].strftime("%Y-%m-%d") if row.get("issue_date") else "-",
                    "due_at": row["due_date"].strftime("%Y-%m-%d") if row.get("due_date") else "-",
                    "issue_date": row["issue_date"].strftime("%Y-%m-%d") if row.get("issue_date") else "-",
                    "due_date": row["due_date"].strftime("%Y-%m-%d") if row.get("due_date") else "-",
                    "status": str(row.get("status", "issued")).title(),
                }
                if row.get("borrowed_by"):
                    item["borrowed_by"] = row["borrowed_by"]
                response.append(item)

            return True, "Issued books loaded successfully.", response
        except Error as exc:
            return False, f"Database error: {exc}", []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def list_due_books(user_id, role, current_date=None):
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            role = (role or "").strip().lower()
            current_date_value = BookService._parse_date(current_date or date.today(), "current_date")
            if role == "student":
                cursor.execute(
                    """
                    SELECT t.id AS transaction_id, t.book_id, t.issue_date, t.due_date,
                           b.title, b.author_name
                    FROM transactions t
                    INNER JOIN students s ON s.id = t.student_id
                    INNER JOIN books b ON b.id = t.book_id
                    WHERE s.user_id = %s
                      AND t.status = 'Issued'
                      AND t.due_date <= %s
                    ORDER BY t.due_date ASC, t.id ASC
                    """,
                    (user_id, current_date_value),
                )
            else:
                cursor.execute(
                    """
                    SELECT t.id AS transaction_id, t.book_id, t.issue_date, t.due_date,
                           b.title, b.author_name
                    FROM transactions t
                    INNER JOIN books b ON b.id = t.book_id
                    WHERE t.status = 'Issued'
                      AND t.due_date <= %s
                    ORDER BY t.due_date ASC, t.id ASC
                    """,
                    (current_date_value,),
                )

            rows = cursor.fetchall()
            due_books = []
            for row in rows:
                due_books.append(
                    {
                        "transaction_id": row["transaction_id"],
                        "book_id": row["book_id"],
                        "title": row["title"],
                        "author_name": row["author_name"],
                        "issue_date": row["issue_date"].strftime("%Y-%m-%d") if row.get("issue_date") else "-",
                        "due_date": row["due_date"].strftime("%Y-%m-%d") if row.get("due_date") else "-",
                        "is_due": True,
                    }
                )

            return True, "Due books loaded successfully.", due_books
        except (Error, ValueError) as exc:
            return False, str(exc), []
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def return_book(book_id, current_date=None, transaction_id=None, requester_user_id=None, requester_role=None):
        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            if not book_id:
                raise ValueError("book_id is required.")

            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)

            role = (requester_role or "").strip().lower()
            transaction_filter = "t.id = %s" if transaction_id else "t.book_id = %s"
            params = [transaction_id or book_id]
            if role == "student":
                transaction_filter += " AND s.user_id = %s"
                params.append(requester_user_id)
            cursor.execute(
                f"""
                SELECT t.id, t.book_id, t.student_id, t.issue_date, t.due_date, t.fine_per_day,
                       s.user_id, b.available_copies, b.total_copies
                FROM transactions t
                INNER JOIN students s ON s.id = t.student_id
                INNER JOIN books b ON b.id = t.book_id
                WHERE {transaction_filter} AND t.status = 'Issued'
                ORDER BY t.id DESC
                LIMIT 1
                """,
                tuple(params),
            )
            transaction = cursor.fetchone()
            if not transaction:
                raise ValueError("No active issued transaction found for this book.")

            current_date_value = BookService._parse_date(current_date or date.today(), "current_date")
            due_date_value = BookService._parse_date(transaction["due_date"], "due_date")
            days_diff, fine_amount = BookService._calculate_fine(
                current_date_value,
                due_date_value,
                float(transaction["fine_per_day"]),
            )
            next_status = "Returned"

            cursor.execute(
                """
                UPDATE transactions
                SET status = %s, return_date = %s, fine_amount = %s
                WHERE id = %s
                """,
                (next_status, current_date_value, fine_amount, transaction["id"]),
            )

            if transaction.get("user_id"):
                cursor.execute(
                    """
                    UPDATE borrow_records
                    SET returned_at = %s, fine_amount = %s, status = %s
                    WHERE user_id = %s AND book_id = %s AND status IN ('issued', 'overdue')
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        BookService._day_end(current_date_value),
                        fine_amount,
                        "returned",
                        transaction["user_id"],
                        book_id,
                    ),
                )

            next_available_copies = min(
                int((transaction.get("available_copies") or 0)) + 1,
                int(transaction.get("total_copies") or 1),
            )
            next_status = BookService._inventory_status(next_available_copies)
            cursor.execute(
                "UPDATE books SET available_copies = %s, status = %s WHERE id = %s",
                (next_available_copies, next_status, transaction["book_id"]),
            )
            connection.commit()

            return True, "Book returned successfully.", {
                "transaction_id": transaction["id"],
                "book_id": transaction["book_id"],
                "student_id": transaction["student_id"],
                "return_date": current_date_value.isoformat(),
                "due_date": due_date_value.isoformat(),
                "days_diff": days_diff,
                "fine_per_day": float(transaction["fine_per_day"]),
                "fine_amount": fine_amount,
                "payment_required": fine_amount > 0,
                "status": next_status,
                "available_copies": next_available_copies,
                "total_copies": int(transaction.get("total_copies") or next_available_copies),
            }
        except (Error, ValueError) as exc:
            if connection:
                connection.rollback()
            return False, str(exc), None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    @staticmethod
    def pay_fine(transaction_id, paid_by_user_id, amount=None):
        if not transaction_id:
            return False, "transaction_id is required.", None
        if not paid_by_user_id:
            return False, "Authenticated user is required.", None

        connection = None
        cursor = None
        try:
            BookService.ensure_library_schema()
            connection = db.get_connection()
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, fine_amount
                FROM transactions
                WHERE id = %s
                LIMIT 1
                """,
                (transaction_id,),
            )
            tx = cursor.fetchone()
            if not tx:
                return False, "Transaction not found.", None

            fine_due = float(tx.get("fine_amount") or 0)
            if fine_due <= 0:
                return False, "No fine due for this transaction.", None

            paid_amount = float(amount) if amount is not None else fine_due
            if paid_amount < fine_due:
                return False, f"Insufficient payment. Fine due is {fine_due:.2f}.", None

            payment_reference = f"PAY-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}-{transaction_id}"
            cursor.execute(
                """
                INSERT INTO fine_payments (
                    transaction_id, paid_by_user_id, amount, payment_reference, payment_mode, payment_status
                ) VALUES (%s, %s, %s, %s, 'simulation', 'paid')
                """,
                (transaction_id, paid_by_user_id, paid_amount, payment_reference),
            )
            connection.commit()
            return True, "Fine payment simulated successfully.", {
                "transaction_id": transaction_id,
                "fine_due": fine_due,
                "paid_amount": paid_amount,
                "payment_reference": payment_reference,
                "payment_status": "paid",
            }
        except Error as exc:
            if connection:
                connection.rollback()
            return False, f"Database error: {exc}", None
        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()
