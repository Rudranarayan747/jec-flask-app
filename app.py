from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key"

UPLOAD_FOLDER = os.path.join(app.root_path, "static/uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "mp4", "avi", "mov"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- Index ----------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------- Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            session["user"] = username
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials", "danger")
            return redirect(url_for("login"))

    return render_template("login.html")

# ---------------- Register ----------------
@app.route("/register")
def register():
    return "Register page coming soon"

# ---------------- Student Dashboard ----------------
@app.route("/student_dashboard")
def student_dashboard():
    return "Student Dashboard coming soon"

# ---------------- Add Notice ----------------
@app.route("/add_notice")
def add_notice():
    return "Notice page coming soon"

# ---------------- Logout ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("index"))

# ---------------- Admin Dashboard ----------------
@app.route("/admin_dashboard")
def admin_dashboard():
    if "user" not in session or session.get("role") != "admin":
        flash("Please log in as admin to access this page", "warning")
        return redirect(url_for("login"))
    return render_template("admin.html")
@app.route("/update_result")
def update_result():
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("login"))
    return "Update Result page coming soon"

# ---------------- Upload Media ----------------
@app.route("/admin/upload", methods=["GET", "POST"])
def upload_media():
    if "user" not in session or session.get("role") != "admin":
        flash("Access denied", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        file = request.files.get("file")
        if not file or file.filename == "":
            flash("No file selected", "danger")
            return redirect(request.url)
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            flash("File uploaded successfully!", "success")
            return redirect(url_for("events"))
        else:
            flash("File type not allowed", "danger")
            return redirect(request.url)

    return render_template("upload_media.html")

# ---------------- Events Gallery ----------------
@app.route("/events")
def events():
    files = []
    if os.path.exists(app.config["UPLOAD_FOLDER"]):
        files = os.listdir(app.config["UPLOAD_FOLDER"])
    return render_template("events.html", files=files)

if __name__ == "__main__":
    app.run(debug=True)
