from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret-key"

# Use PostgreSQL on Render (set DATABASE_URL in environment variables)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///jec.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Models
class Student(UserMixin, db.Model):
    id = db.Column(db.String(50), primary_key=True)  # registration number
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default="student")
    result = db.Column(db.String(50))

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        reg = request.form["reg"]
        password = request.form["password"]
        user = Student.query.get(reg)
        if user and user.password == password:
            login_user(user)
            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("student_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return "Access denied"
    notices = Notice.query.all()
    students = Student.query.all()
    return render_template("admin.html", notices=notices, students=students)

@app.route("/admin/update_result/<reg>", methods=["GET", "POST"])
@login_required
def update_result(reg):
    if current_user.role != "admin":
        return "Access denied"
    student = Student.query.get(reg)
    if not student:
        return "Student not found"
    if request.method == "POST":
        student.result = request.form["result"]
        db.session.commit()
        flash(f"Result updated for {student.name}", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("update_result.html", student=student)

@app.route("/admin/delete_student/<reg>")
@login_required
def delete_student(reg):
    if current_user.role != "admin":
        return "Access denied"
    student = Student.query.get(reg)
    if student:
        db.session.delete(student)
        db.session.commit()
        flash(f"Student {student.name} deleted.", "warning")
    return redirect(url_for("admin_dashboard"))

@app.route("/student")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return "Access denied"
    notices = Notice.query.all()
    return render_template("student.html", student=current_user, notices=notices)

@app.route("/admin/add_notice", methods=["GET", "POST"])
@login_required
def add_notice():
    if current_user.role != "admin":
        return "Access denied"
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        db.session.add(Notice(title=title, content=content))
        db.session.commit()
        flash("Notice added successfully", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("add_notice.html")

# Initialize DB with default admin
with app.app_context():
    db.create_all()
    if not Student.query.get("admin"):
        db.session.add(Student(id="admin", name="Administrator", password="admin123", role="admin"))
    if not Notice.query.first():
        db.session.add(Notice(title="Upcoming Internal 1 Exam",
                             content="Internal 1 for 2nd Semester will be held from 24th March to 26th March."))
    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
