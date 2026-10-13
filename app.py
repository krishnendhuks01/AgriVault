
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)
from functools import wraps
from werkzeug.utils import secure_filename
import mysql.connector
import os
import uuid
import html
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)
app.secret_key = "agrivault_change_this_secret_key"

# Upload settings
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

ALLOWED_IMAGES = {"jpg", "jpeg", "png", "webp"}
ALLOWED_PDFS = {"pdf"}


# MySQL Database Connection
db = mysql.connector.connect(
    host="localhost",
    port=3307,
    user="root",
    password="YOUR_PASSWORD",
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


def admin_required(view_function):
    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if session.get("role") != "Admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))

        return view_function(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    return render_template("index.html")


# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "Passwords do not match"

        cursor = db.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        if cursor.fetchone():
            cursor.close()
            return "Email already registered"

        cursor.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, 'User')
        """, (name, email, password))

        db.commit()
        cursor.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# User Dashboard
@app.route("/user_dashboard")
def user_dashboard():
    return render_template("user_dashboard.html")


# NLP / Article Query

# NLP / Article Query
@app.route("/query", methods=["GET", "POST"])
def query():
    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if not question:
            flash("Please enter an agricultural question.", "warning")
            return render_template("query.html")

        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT article_id, title, content, keywords,
                   image_path, pdf_path
            FROM articles
        """)

        articles = cursor.fetchall()
        cursor.close()

        if not articles:
            flash(
                "No agricultural articles are available yet. "
                "Please check back later.",
                "warning"
            )
            return render_template("query.html")

        # Prepare searchable text for each article
        documents = []

        for article in articles:
            text = " ".join([
                article.get("title") or "",
                article.get("keywords") or "",
                article.get("content") or ""
            ])
            documents.append(text)

        # TF-IDF converts text into numerical vectors
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True
        )

        try:
            tfidf_matrix = vectorizer.fit_transform(
                documents + [question]
            )
        except ValueError:
            flash(
                "Not enough searchable text is available. "
                "Please add article content or keywords.",
                "warning"
            )
            return render_template("query.html")

        # Compare the question with all articles
        question_vector = tfidf_matrix[-1]
        article_vectors = tfidf_matrix[:-1]

        scores = cosine_similarity(
            question_vector,
            article_vectors
        ).flatten()

        best_index = scores.argmax()
        best_score = float(scores[best_index])

        # Avoid displaying an unrelated article
        if best_score < 0.05:
            flash(
                "No relevant agricultural information found. "
                "Try different keywords or a more specific question.",
                "warning"
            )
            return render_template("query.html")

        article = articles[best_index]

        title = html.escape(article.get("title") or "")
        content = html.escape(article.get("content") or "")
        content = content.replace("\n", "<br>")

        image_html = ""
        pdf_html = ""

        if article.get("image_path"):
            image_url = url_for(
                "static",
                filename=article["image_path"]
            )
            image_html = f"""
                <div class="mt-4">
                    <h5>🖼️ Related Image</h5>
                    <img src="{image_url}"
                         alt="Agricultural article image"
                         class="img-fluid rounded"
                         style="max-height:400px">
                </div>
            """

        if article.get("pdf_path"):
            pdf_url = url_for(
                "static",
                filename=article["pdf_path"]
            )
            pdf_html = f"""
                <div class="mt-4">
                    <a href="{pdf_url}"
                       target="_blank"
                       rel="noopener noreferrer"
                       class="btn btn-outline-danger">
                        📄 Open / View PDF
                    </a>
                </div>
            """

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport"
                  content="width=device-width, initial-scale=1.0">
            <title>Answer - AgriVault</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css"
                  rel="stylesheet">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: #f4f8f3;
                }}
                .navbar {{ background: #2e7d32; }}
                .navbar-brand {{
                    color: white !important;
                    font-weight: bold;
                }}
                .answer-box {{
                    max-width: 800px;
                    margin: 50px auto;
                    background: white;
                    padding: 30px;
                    border-radius: 18px;
                    box-shadow: 0 8px 25px rgba(0,0,0,.08);
                }}
                .answer-title {{
                    color: #2e7d32;
                    font-weight: bold;
                }}
                .answer-content {{
                    background: #f4f8f3;
                    padding: 22px;
                    border-radius: 12px;
                    margin-top: 20px;
                    line-height: 1.8;
                    overflow-wrap: anywhere;
                }}
            </style>
        </head>
        <body>
            <nav class="navbar navbar-dark">
                <div class="container">
                    <a class="navbar-brand"
                       href="/user_dashboard">🌾 AgriVault</a>
                    <a href="/user_dashboard"
                       class="text-white text-decoration-none">
                        ← Dashboard
                    </a>
                </div>
            </nav>

            <div class="container">
                <div class="answer-box">
                    <h2 class="answer-title text-center">
                        🤖🌱 {title}
                    </h2>

                    <div class="answer-content">
                        <h5>📖 Agricultural Information</h5>
                        <p class="mb-0">{content}</p>
                    </div>

                    {image_html}
                    {pdf_html}

                    <div class="text-center mt-4">
                        <a href="/query" class="btn btn-success">
                            🔍 Ask Another Question
                        </a>
                        <a href="/user_dashboard"
                           class="btn btn-outline-success">
                            ← Dashboard
                        </a>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    return render_template("query.html")



# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor()
        cursor.execute("""
            SELECT user_id, name, email, password, role
            FROM users
            WHERE email = %s AND password = %s
        """, (email, password))

        user = cursor.fetchone()
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

    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM categories")
    total_categories = cursor.fetchone()[0]

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
    return redirect(url_for("login"))


# View all articles
@app.route("/admin/articles")
@admin_required
def manage_articles():
    cursor = db.cursor()

    cursor.execute("""
        SELECT a.article_id, a.title, a.keywords,
               c.category_name, a.image_path, a.pdf_path
        FROM articles a
        LEFT JOIN categories c
          ON a.category_id = c.category_id
        ORDER BY a.article_id DESC
    """)

    articles = cursor.fetchall()
    cursor.close()

    return render_template(
        "manage_articles.html",
        articles=articles
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
        cursor.execute("""
            INSERT INTO articles
                (title, content, keywords, category_id,
                 created_by, image_path, pdf_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            title, content, keywords, category_id,
            session["user_id"], image_path, pdf_path
        ))

        db.commit()
        cursor.close()

        flash("Article and attachments saved!", "success")
        return redirect(url_for("manage_articles"))

    cursor = db.cursor()
    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
        ORDER BY category_name
    """)

    categories = cursor.fetchall()
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

    cursor.execute("""
        SELECT article_id, title, content, keywords,
               category_id, image_path, pdf_path
        FROM articles
        WHERE article_id = %s
    """, (article_id,))

    article = cursor.fetchone()
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
            title, content, keywords, category_id,
            image_path, pdf_path, article_id
        ))

        db.commit()
        cursor.close()

        flash("Article updated successfully!", "success")
        return redirect(url_for("manage_articles"))

    cursor = db.cursor()
    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
        ORDER BY category_name
    """)

    categories = cursor.fetchall()
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
    cursor.execute(
        "DELETE FROM articles WHERE article_id = %s",
        (article_id,)
    )
    db.commit()
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


@app.route("/admin/policies")
@admin_required
def manage_policies():
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM government_policies ORDER BY policy_id DESC"
    )
    policies = cursor.fetchall()
    cursor.close()
    return render_template(
        "manage_policies.html",
        policies=policies
    )


@app.route("/admin/policies/add", methods=["GET", "POST"])
@admin_required
def add_policy():
    cursor = db.cursor(dictionary=True)
    if request.method == "POST":
        title = request.form["title"].strip()
        description = request.form["description"].strip()
        department = request.form.get("department", "").strip()
        eligibility = request.form.get("eligibility", "").strip()
        benefits = request.form.get("benefits", "").strip()
        official_url = request.form.get("official_url", "").strip()
        created_by = session.get("user_id")

        cursor.execute("""
            INSERT INTO government_policies
            (title, description, department, eligibility,
             benefits, official_url, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            title, description, department, eligibility,
            benefits, official_url, created_by
        ))
        db.commit()
        cursor.close()
        flash("Government policy added successfully!", "success")
        return redirect(url_for("manage_policies"))

    cursor.close()
    return render_template("policy_form.html", policy=None)



# Edit Government Policy
@app.route(
    "/admin/policies/edit/<int:policy_id>",
    methods=["GET", "POST"]
)
@admin_required
def edit_policy(policy_id):
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM government_policies WHERE policy_id = %s",
        (policy_id,)
    )
    policy = cursor.fetchone()

    if not policy:
        cursor.close()
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
            cursor.close()
            flash("Title and description are required.", "danger")
            return redirect(
                url_for("edit_policy", policy_id=policy_id)
            )

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
            title, description, department, eligibility,
            benefits, official_url, policy_id
        ))

        db.commit()
        cursor.close()

        flash("Policy updated successfully!", "success")
        return redirect(url_for("manage_policies"))

    cursor.close()
    return render_template("policy_form.html", policy=policy)


# Delete Government Policy
@app.route(
    "/admin/policies/delete/<int:policy_id>",
    methods=["POST"]
)
@admin_required
def delete_policy(policy_id):
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM government_policies WHERE policy_id = %s",
        (policy_id,)
    )
    db.commit()
    cursor.close()

    flash("Policy deleted successfully!", "success")
    return redirect(url_for("manage_policies"))



# User Side - View Government Policies
@app.route("/user/policies")
def user_policies():
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT policy_id, title, description, department,
               eligibility, benefits, official_url
        FROM government_policies
        ORDER BY policy_id DESC
    """)

    policies = cursor.fetchall()
    cursor.close()

    return render_template(
        "user_policies.html",
        policies=policies
    )


if __name__ == "__main__":
    app.run(debug=True)
