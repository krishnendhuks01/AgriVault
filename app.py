
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from functools import wraps
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import mysql.connector
import os
import uuid
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Upload settings
UPLOAD_FOLDER = os.path.join(
    app.root_path, "static", "uploads"
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PDFS = {"pdf"}


# MySQL Database Connection
db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password=os.getenv("DB_PASSWORD"),
    database="agrivault_db"
)


# File upload helper
def save_upload(upload, allowed_extensions):
    if not upload or not upload.filename:
        return None

    filename = secure_filename(upload.filename)

    if "." not in filename:
        raise ValueError("Invalid file name.")

    extension = filename.rsplit(".", 1)[1].lower()

    if extension not in allowed_extensions:
        raise ValueError(
            "Invalid file type. Please upload an allowed file."
        )

    unique_name = f"{uuid.uuid4().hex}.{extension}"
    upload_path = os.path.join(UPLOAD_FOLDER, unique_name)

    upload.save(upload_path)

    return f"uploads/{unique_name}"


# Admin access protection
def admin_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if session.get("role") != "Admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapper


# Home
@app.route("/")
def home():
    return render_template("index.html")


# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "Passwords do not match"

        cursor = db.cursor()

        try:
            cursor.execute(
                "SELECT user_id FROM users WHERE email = %s",
                (email,)
            )

            if cursor.fetchone():
                return "Email already registered"

            cursor.execute("""
                INSERT INTO users (name, email, password, role)
                VALUES (%s, %s, %s, 'User')
            """, (name, email, password))

            db.commit()

        finally:
            cursor.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# User Dashboard
@app.route("/user_dashboard")
def user_dashboard():
    return render_template("user_dashboard.html")


# ==================================================
# NLP / ARTICLE KEYWORD SEARCH
# ==================================================

# NLP / Article Query
@app.route("/query", methods=["GET", "POST"])
def query():
    if request.method == "GET":
        return render_template("query.html")

    question = request.form.get("question", "").strip()

    if not question:
        return render_template(
            "query.html",
            question=question,
            results=[],
            error="Please enter your search keywords."
        )

    # Extract all searched words
    query_words = set(
        re.findall(r"[a-z0-9]+", question.lower())
    )

    if not query_words:
        return render_template(
            "query.html",
            question=question,
            results=[],
            error="Please enter valid search keywords."
        )

    cursor = None

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT article_id, title, content, keywords,
                   image_path, pdf_path
            FROM articles
            ORDER BY article_id DESC
        """)

        articles_list = cursor.fetchall()

    except mysql.connector.Error:
        app.logger.exception("Article search database error")
        return render_template(
            "query.html",
            question=question,
            results=[],
            error="Database search failed. Please try again."
        )

    finally:
        if cursor is not None:
            cursor.close()

    results = []

    for article in articles_list:
        article_keywords = str(
            article.get("keywords") or ""
        ).lower()

        keyword_words = set(
            re.findall(r"[a-z0-9]+", article_keywords)
        )

        # Match if ANY searched keyword exists in the article
        if query_words.intersection(keyword_words):
            results.append({
                "type": "article",
                "data": article,
                "similarity_score": 1.0
            })

    if not results:
        return render_template(
            "query.html",
            question=question,
            results=[],
            error="No articles found for the entered keywords."
        )

    # Return every matching article
    return render_template(
        "query.html",
        question=question,
        results=results
    )



# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"]

        cursor = db.cursor()

        try:
            cursor.execute("""
                SELECT user_id, name, email, password, role
                FROM users
                WHERE email = %s AND password = %s
            """, (email, password))

            user = cursor.fetchone()

        finally:
            cursor.close()

        if user:
            session.clear()
            session["user_id"] = user[0]
            session["name"] = user[1]
            session["email"] = user[2]
            session["role"] = user[4]

            if user[4] == "Admin":
                return redirect(url_for("admin_dashboard"))

            return redirect(url_for("user_dashboard"))

        flash("Invalid email or password", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


# Admin Dashboard
@app.route("/admin_dashboard")
@admin_required
def admin_dashboard():
    cursor = db.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM categories")
        total_categories = cursor.fetchone()[0]

    finally:
        cursor.close()

    return render_template(
        "admin_dashboard.html",
        total_articles=total_articles,
        total_categories=total_categories
    )


# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ==================================================
# ADMIN ARTICLE MANAGEMENT
# ==================================================

# View all articles
@app.route("/admin/articles")
@admin_required
def manage_articles():
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT a.article_id, a.title, a.keywords,
                   c.category_name, a.image_path, a.pdf_path
            FROM articles a
            LEFT JOIN categories c
              ON a.category_id = c.category_id
            ORDER BY a.article_id DESC
        """)

        articles_list = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "manage_articles.html",
        articles=articles_list
    )


# Add article with optional image and PDF
@app.route("/admin/articles/add", methods=["GET", "POST"])
@admin_required
def add_article():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        keywords = request.form.get("keywords", "").strip()
        category_id = request.form.get("category_id", "")

        if not title or not content or not category_id:
            flash(
                "Title, content and category are required.",
                "danger"
            )
            return redirect(url_for("add_article"))

        try:
            image_path = save_upload(
                request.files.get("image_file"),
                ALLOWED_IMAGES
            )

            pdf_path = save_upload(
                request.files.get("pdf_file"),
                ALLOWED_PDFS
            )

        except ValueError as error:
            flash(str(error), "danger")
            return redirect(url_for("add_article"))

        cursor = db.cursor()

        try:
            cursor.execute("""
                INSERT INTO articles
                    (title, content, keywords, category_id,
                     created_by, image_path, pdf_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                title,
                content,
                keywords,
                category_id,
                session["user_id"],
                image_path,
                pdf_path
            ))

            db.commit()

        finally:
            cursor.close()

        flash("Article and attachments saved!", "success")
        return redirect(url_for("manage_articles"))

    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """)

        categories = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "article_form.html",
        categories=categories,
        article=None,
        page_title="Add New Article"
    )


# Edit article and optionally replace attachments
@app.route(
    "/admin/articles/edit/<int:article_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_article(article_id):
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT article_id, title, content, keywords,
                   category_id, image_path, pdf_path
            FROM articles
            WHERE article_id = %s
        """, (article_id,))

        article = cursor.fetchone()

    finally:
        cursor.close()

    if not article:
        flash("Article not found.", "danger")
        return redirect(url_for("manage_articles"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        keywords = request.form.get("keywords", "").strip()
        category_id = request.form.get("category_id", "")

        if not title or not content or not category_id:
            flash(
                "Title, content and category are required.",
                "danger"
            )
            return redirect(
                url_for("edit_article", article_id=article_id)
            )

        image_path = article[5]
        pdf_path = article[6]

        try:
            new_image = save_upload(
                request.files.get("image_file"),
                ALLOWED_IMAGES
            )

            new_pdf = save_upload(
                request.files.get("pdf_file"),
                ALLOWED_PDFS
            )

        except ValueError as error:
            flash(str(error), "danger")
            return redirect(
                url_for("edit_article", article_id=article_id)
            )

        # Keep the old file if no replacement is uploaded
        if new_image:
            image_path = new_image

        if new_pdf:
            pdf_path = new_pdf

        cursor = db.cursor()

        try:
            cursor.execute("""
                UPDATE articles
                SET title = %s,
                    content = %s,
                    keywords = %s,
                    category_id = %s,
                    image_path = %s,
                    pdf_path = %s
                WHERE article_id = %s
            """, (
                title,
                content,
                keywords,
                category_id,
                image_path,
                pdf_path,
                article_id
            ))

            db.commit()

        finally:
            cursor.close()

        flash("Article updated successfully!", "success")
        return redirect(url_for("manage_articles"))

    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT category_id, category_name
            FROM categories
            ORDER BY category_name
        """)

        categories = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "article_form.html",
        categories=categories,
        article=article,
        page_title="Edit Article"
    )


# Delete article
@app.route(
    "/admin/articles/delete/<int:article_id>",
    methods=["POST"]
)
@admin_required
def delete_article(article_id):
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM articles WHERE article_id = %s",
            (article_id,)
        )
        db.commit()

    finally:
        cursor.close()

    flash("Article deleted successfully!", "success")
    return redirect(url_for("manage_articles"))


# Handle oversized uploads
@app.errorhandler(413)
def file_too_large(error):
    return (
        "Upload too large. Please keep the total upload under 15 MB.",
        413
    )


# ==================================================
# ADMIN GOVERNMENT POLICY MANAGEMENT
# ==================================================

@app.route("/admin/policies")
@admin_required
def manage_policies():
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT *
            FROM government_policies
            ORDER BY policy_id DESC
        """)

        policies = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "manage_policies.html",
        policies=policies
    )


# Add Government Policy
@app.route("/admin/policies/add", methods=["GET", "POST"])
@admin_required
def add_policy():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "").strip()
        eligibility = request.form.get("eligibility", "").strip()
        benefits = request.form.get("benefits", "").strip()
        official_url = request.form.get("official_url", "").strip()
        created_by = session.get("user_id")

        if not title or not description:
            flash("Title and description are required.", "danger")
            return redirect(url_for("add_policy"))

        cursor = db.cursor()

        try:
            cursor.execute("""
                INSERT INTO government_policies
                    (title, description, department, eligibility,
                     benefits, official_url, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                title,
                description,
                department,
                eligibility,
                benefits,
                official_url,
                created_by
            ))

            db.commit()

        finally:
            cursor.close()

        flash("Government policy added successfully!", "success")
        return redirect(url_for("manage_policies"))

    return render_template("policy_form.html", policy=None)


# Edit Government Policy
@app.route(
    "/admin/policies/edit/<int:policy_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_policy(policy_id):
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute(
            "SELECT * FROM government_policies WHERE policy_id = %s",
            (policy_id,)
        )

        policy = cursor.fetchone()

    finally:
        cursor.close()

    if not policy:
        flash("Policy not found.", "danger")
        return redirect(url_for("manage_policies"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department = request.form.get("department", "").strip()
        eligibility = request.form.get("eligibility", "").strip()
        benefits = request.form.get("benefits", "").strip()
        official_url = request.form.get("official_url", "").strip()

        if not title or not description:
            flash("Title and description are required.", "danger")
            return redirect(
                url_for("edit_policy", policy_id=policy_id)
            )

        cursor = db.cursor()

        try:
            cursor.execute("""
                UPDATE government_policies
                SET title = %s,
                    description = %s,
                    department = %s,
                    eligibility = %s,
                    benefits = %s,
                    official_url = %s
                WHERE policy_id = %s
            """, (
                title,
                description,
                department,
                eligibility,
                benefits,
                official_url,
                policy_id
            ))

            db.commit()

        finally:
            cursor.close()

        flash("Policy updated successfully!", "success")
        return redirect(url_for("manage_policies"))

    return render_template("policy_form.html", policy=policy)


# Delete Government Policy
@app.route(
    "/admin/policies/delete/<int:policy_id>",
    methods=["POST"]
)
@admin_required
def delete_policy(policy_id):
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM government_policies WHERE policy_id = %s",
            (policy_id,)
        )
        db.commit()

    finally:
        cursor.close()

    flash("Policy deleted successfully!", "success")
    return redirect(url_for("manage_policies"))


# ==================================================
# USER SIDE - GOVERNMENT POLICIES
# ==================================================

@app.route("/user/policies")
def user_policies():
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT policy_id, title, description, department,
                   eligibility, benefits, official_url
            FROM government_policies
            ORDER BY policy_id DESC
        """)

        policies = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "user_policies.html",
        policies=policies
    )


# ==================================================
# USER SIDE - VIEW ALL ARTICLES
# ==================================================

@app.route("/articles")
def articles():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT a.article_id, a.title, a.content, a.keywords,
                   a.image_path, a.pdf_path, a.category_id,
                   c.category_name
            FROM articles a
            LEFT JOIN categories c
              ON a.category_id = c.category_id
            ORDER BY a.article_id DESC
        """)

        articles_list = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "articles.html",
        articles=articles_list
    )


# ==================================================
# USER SIDE - PEST MANAGEMENT ARTICLES
# ==================================================

@app.route("/pest-articles")
def pest_articles():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT a.article_id, a.title, a.content, a.keywords,
                   a.image_path, a.pdf_path, c.category_name
            FROM articles a
            JOIN categories c
              ON a.category_id = c.category_id
            WHERE LOWER(c.category_name) = %s
            ORDER BY a.article_id DESC
        """, ("pest management",))

        articles_list = cursor.fetchall()

    finally:
        cursor.close()

    return render_template(
        "articles.html",
        articles=articles_list
    )


# Run Flask application
if __name__ == "__main__":
    app.run(debug=True)
