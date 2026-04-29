from datetime import datetime
from functools import wraps
import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "library-management-secret-key-change-me")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "library.db")


# -----------------------------
# Database helpers
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT NOT NULL,
            isbn TEXT UNIQUE NOT NULL,
            shelf_no TEXT DEFAULT 'A-01',
            total_copies INTEGER NOT NULL CHECK(total_copies >= 0),
            available_copies INTEGER NOT NULL CHECK(available_copies >= 0),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('pending', 'issued', 'returned', 'rejected')),
            requested_at TEXT DEFAULT CURRENT_TIMESTAMP,
            issued_at TEXT,
            returned_at TEXT,
            remarks TEXT DEFAULT '',
            FOREIGN KEY(student_id) REFERENCES users(id),
            FOREIGN KEY(book_id) REFERENCES books(id)
        )
        """
    )

    admin = cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
    if not admin:
        cur.execute(
            """
            INSERT INTO users (name, email, password, role)
            VALUES (?, ?, ?, ?)
            """,
            (
                "Library Admin",
                "admin@library.com",
                generate_password_hash("admin123"),
                "admin",
            ),
        )

    book_count = cur.execute("SELECT COUNT(*) AS total FROM books").fetchone()["total"]
    if book_count == 0:
        sample_books = [
            ("Python Programming", "Guido van Rossum", "Programming", "PY-101", "A-01", 6, 6),
            ("Flask Web Development", "Miguel Grinberg", "Web Development", "FL-202", "A-02", 4, 4),
            ("Database Management Systems", "Raghu Ramakrishnan", "Database", "DB-303", "B-01", 5, 5),
            ("Data Structures Using Python", "Narasimha Karumanchi", "DSA", "DS-404", "B-02", 7, 7),
            ("Operating System Concepts", "Silberschatz", "Computer Science", "OS-505", "C-01", 3, 3),
            ("Computer Networks", "Andrew S. Tanenbaum", "Networking", "CN-606", "C-02", 4, 4),
            ("Clean Code", "Robert C. Martin", "Software Engineering", "CC-707", "D-01", 3, 3),
            ("Artificial Intelligence", "Stuart Russell", "AI", "AI-808", "D-02", 2, 2),
        ]
        cur.executemany(
            """
            INSERT INTO books (title, author, category, isbn, shelf_no, total_copies, available_copies)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            sample_books,
        )

    conn.commit()
    conn.close()


@app.before_request
def setup_database():
    init_db()


# -----------------------------
# Auth helpers
# -----------------------------
def login_required(role=None):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login to continue.", "error")
                return redirect(url_for("index"))
            if role and session.get("role") != role:
                flash("You do not have permission to access that page.", "error")
                return redirect(url_for("index"))
            return view_func(*args, **kwargs)

        return wrapped_view

    return decorator


def current_user():
    if "user_id" not in session:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user


# -----------------------------
# Public routes
# -----------------------------
@app.route("/")
def index():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return render_template("index.html")


@app.route("/signup/<role>", methods=["GET", "POST"])
def signup(role):
    if role not in ["admin", "student"]:
        flash("Invalid account type.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("signup", role=role))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("signup", role=role))

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return redirect(url_for("signup", role=role))

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            flash("This email is already registered.", "error")
            return redirect(url_for("signup", role=role))

        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), role),
        )
        conn.commit()
        conn.close()

        flash(f"{role.capitalize()} account created. Please login.", "success")
        return redirect(url_for("login", role=role))

    return render_template("signup.html", role=role)


@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if role not in ["admin", "student"]:
        flash("Invalid login type.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND role = ?", (email, role)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            flash("Login successful.", "success")
            return redirect(url_for("admin_dashboard" if role == "admin" else "student_dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html", role=role)


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


# -----------------------------
# Admin routes
# -----------------------------
@app.route("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    conn = get_db_connection()
    stats = {
        "books": conn.execute("SELECT COUNT(*) AS count FROM books").fetchone()["count"],
        "students": conn.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'student'").fetchone()["count"],
        "pending": conn.execute("SELECT COUNT(*) AS count FROM transactions WHERE status = 'pending'").fetchone()["count"],
        "issued": conn.execute("SELECT COUNT(*) AS count FROM transactions WHERE status = 'issued'").fetchone()["count"],
    }

    pending_requests = conn.execute(
        """
        SELECT t.*, u.name AS student_name, u.email AS student_email, b.title, b.author, b.available_copies
        FROM transactions t
        JOIN users u ON u.id = t.student_id
        JOIN books b ON b.id = t.book_id
        WHERE t.status = 'pending'
        ORDER BY t.requested_at DESC
        """
    ).fetchall()

    issued_books = conn.execute(
        """
        SELECT t.*, u.name AS student_name, u.email AS student_email, b.title, b.author
        FROM transactions t
        JOIN users u ON u.id = t.student_id
        JOIN books b ON b.id = t.book_id
        WHERE t.status = 'issued'
        ORDER BY t.issued_at DESC
        """
    ).fetchall()

    recent_activity = conn.execute(
        """
        SELECT t.*, u.name AS student_name, b.title
        FROM transactions t
        JOIN users u ON u.id = t.student_id
        JOIN books b ON b.id = t.book_id
        ORDER BY t.id DESC
        LIMIT 8
        """
    ).fetchall()
    conn.close()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        pending_requests=pending_requests,
        issued_books=issued_books,
        recent_activity=recent_activity,
    )


@app.route("/admin/books")
@login_required("admin")
def admin_books():
    query = request.args.get("q", "").strip()
    conn = get_db_connection()
    if query:
        like = f"%{query}%"
        books = conn.execute(
            """
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR category LIKE ? OR isbn LIKE ? OR shelf_no LIKE ?
            ORDER BY id DESC
            """,
            (like, like, like, like, like),
        ).fetchall()
    else:
        books = conn.execute("SELECT * FROM books ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("admin/books.html", books=books, query=query)


@app.route("/admin/books/add", methods=["GET", "POST"])
@login_required("admin")
def add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        isbn = request.form.get("isbn", "").strip()
        shelf_no = request.form.get("shelf_no", "A-01").strip() or "A-01"
        total_copies = int(request.form.get("total_copies", 0))

        if not title or not author or not category or not isbn or total_copies < 1:
            flash("Please enter valid book details.", "error")
            return redirect(url_for("add_book"))

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO books (title, author, category, isbn, shelf_no, total_copies, available_copies)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (title, author, category, isbn, shelf_no, total_copies, total_copies),
            )
            conn.commit()
            flash("Book added successfully.", "success")
            return redirect(url_for("admin_books"))
        except sqlite3.IntegrityError:
            flash("ISBN already exists. Use a unique ISBN.", "error")
        finally:
            conn.close()

    return render_template("admin/book_form.html", book=None, mode="add")


@app.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def edit_book(book_id):
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if not book:
        conn.close()
        flash("Book not found.", "error")
        return redirect(url_for("admin_books"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        category = request.form.get("category", "").strip()
        isbn = request.form.get("isbn", "").strip()
        shelf_no = request.form.get("shelf_no", "A-01").strip() or "A-01"
        total_copies = int(request.form.get("total_copies", 0))

        issued_count = book["total_copies"] - book["available_copies"]
        if total_copies < issued_count:
            conn.close()
            flash(f"Total copies cannot be less than currently issued copies: {issued_count}.", "error")
            return redirect(url_for("edit_book", book_id=book_id))

        new_available = total_copies - issued_count
        try:
            conn.execute(
                """
                UPDATE books
                SET title = ?, author = ?, category = ?, isbn = ?, shelf_no = ?, total_copies = ?, available_copies = ?
                WHERE id = ?
                """,
                (title, author, category, isbn, shelf_no, total_copies, new_available, book_id),
            )
            conn.commit()
            flash("Book updated successfully.", "success")
            return redirect(url_for("admin_books"))
        except sqlite3.IntegrityError:
            flash("ISBN already exists. Use a unique ISBN.", "error")
        finally:
            conn.close()

    conn.close()
    return render_template("admin/book_form.html", book=book, mode="edit")


@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
@login_required("admin")
def delete_book(book_id):
    conn = get_db_connection()
    active = conn.execute(
        "SELECT COUNT(*) AS count FROM transactions WHERE book_id = ? AND status IN ('pending', 'issued')",
        (book_id,),
    ).fetchone()["count"]

    if active > 0:
        conn.close()
        flash("Cannot delete this book because it has active requests or issued copies.", "error")
        return redirect(url_for("admin_books"))

    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    flash("Book deleted successfully.", "success")
    return redirect(url_for("admin_books"))


@app.route("/admin/request/<int:transaction_id>/<action>", methods=["POST"])
@login_required("admin")
def handle_request(transaction_id, action):
    if action not in ["approve", "reject"]:
        flash("Invalid action.", "error")
        return redirect(url_for("admin_dashboard"))

    conn = get_db_connection()
    transaction = conn.execute(
        """
        SELECT t.*, b.available_copies
        FROM transactions t
        JOIN books b ON b.id = t.book_id
        WHERE t.id = ? AND t.status = 'pending'
        """,
        (transaction_id,),
    ).fetchone()

    if not transaction:
        conn.close()
        flash("Request not found or already handled.", "error")
        return redirect(url_for("admin_dashboard"))

    if action == "approve":
        if transaction["available_copies"] <= 0:
            conn.close()
            flash("No copies available for this book.", "error")
            return redirect(url_for("admin_dashboard"))

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE transactions SET status = 'issued', issued_at = ?, remarks = ? WHERE id = ?",
            (now, "Approved and issued by admin", transaction_id),
        )
        conn.execute(
            "UPDATE books SET available_copies = available_copies - 1 WHERE id = ?",
            (transaction["book_id"],),
        )
        flash("Book request approved and issued.", "success")
    else:
        conn.execute(
            "UPDATE transactions SET status = 'rejected', remarks = ? WHERE id = ?",
            ("Request rejected by admin", transaction_id),
        )
        flash("Book request rejected.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/return/<int:transaction_id>", methods=["POST"])
@login_required("admin")
def mark_returned(transaction_id):
    conn = get_db_connection()
    transaction = conn.execute(
        "SELECT * FROM transactions WHERE id = ? AND status = 'issued'",
        (transaction_id,),
    ).fetchone()

    if not transaction:
        conn.close()
        flash("Issued record not found.", "error")
        return redirect(url_for("admin_dashboard"))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE transactions SET status = 'returned', returned_at = ?, remarks = ? WHERE id = ?",
        (now, "Marked as returned by admin", transaction_id),
    )
    conn.execute(
        "UPDATE books SET available_copies = available_copies + 1 WHERE id = ?",
        (transaction["book_id"],),
    )
    conn.commit()
    conn.close()
    flash("Book marked as returned.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/students")
@login_required("admin")
def students():
    conn = get_db_connection()
    students_list = conn.execute(
        """
        SELECT u.*,
               COUNT(t.id) AS total_requests,
               SUM(CASE WHEN t.status = 'issued' THEN 1 ELSE 0 END) AS active_issued
        FROM users u
        LEFT JOIN transactions t ON t.student_id = u.id
        WHERE u.role = 'student'
        GROUP BY u.id
        ORDER BY u.id DESC
        """
    ).fetchall()
    conn.close()
    return render_template("admin/students.html", students=students_list)


# -----------------------------
# Student routes
# -----------------------------
@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    user_id = session["user_id"]
    query = request.args.get("q", "").strip()

    conn = get_db_connection()
    if query:
        like = f"%{query}%"
        books = conn.execute(
            """
            SELECT * FROM books
            WHERE title LIKE ? OR author LIKE ? OR category LIKE ? OR isbn LIKE ?
            ORDER BY title ASC
            """,
            (like, like, like, like),
        ).fetchall()
    else:
        books = conn.execute("SELECT * FROM books ORDER BY title ASC").fetchall()

    my_transactions = conn.execute(
        """
        SELECT t.*, b.title, b.author, b.category, b.isbn
        FROM transactions t
        JOIN books b ON b.id = t.book_id
        WHERE t.student_id = ?
        ORDER BY t.id DESC
        """,
        (user_id,),
    ).fetchall()

    active_book_ids = {
        row["book_id"]
        for row in conn.execute(
            "SELECT book_id FROM transactions WHERE student_id = ? AND status IN ('pending', 'issued')",
            (user_id,),
        ).fetchall()
    }

    stats = {
        "pending": conn.execute(
            "SELECT COUNT(*) AS count FROM transactions WHERE student_id = ? AND status = 'pending'",
            (user_id,),
        ).fetchone()["count"],
        "issued": conn.execute(
            "SELECT COUNT(*) AS count FROM transactions WHERE student_id = ? AND status = 'issued'",
            (user_id,),
        ).fetchone()["count"],
        "returned": conn.execute(
            "SELECT COUNT(*) AS count FROM transactions WHERE student_id = ? AND status = 'returned'",
            (user_id,),
        ).fetchone()["count"],
    }
    conn.close()

    return render_template(
        "student/dashboard.html",
        books=books,
        transactions=my_transactions,
        active_book_ids=active_book_ids,
        query=query,
        stats=stats,
    )


@app.route("/student/request/<int:book_id>", methods=["POST"])
@login_required("student")
def request_book(book_id):
    user_id = session["user_id"]
    conn = get_db_connection()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()

    if not book:
        conn.close()
        flash("Book not found.", "error")
        return redirect(url_for("student_dashboard"))

    existing = conn.execute(
        """
        SELECT id FROM transactions
        WHERE student_id = ? AND book_id = ? AND status IN ('pending', 'issued')
        """,
        (user_id, book_id),
    ).fetchone()

    if existing:
        conn.close()
        flash("You already have an active request or issued copy for this book.", "error")
        return redirect(url_for("student_dashboard"))

    if book["available_copies"] <= 0:
        conn.close()
        flash("This book is currently not available.", "error")
        return redirect(url_for("student_dashboard"))

    conn.execute(
        "INSERT INTO transactions (student_id, book_id, status, remarks) VALUES (?, ?, 'pending', ?)",
        (user_id, book_id, "Waiting for admin approval"),
    )
    conn.commit()
    conn.close()
    flash("Book request sent to admin.", "success")
    return redirect(url_for("student_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
