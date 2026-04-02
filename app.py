from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import extract
from datetime import datetime
import os
import io
import xlsxwriter
from fpdf import FPDF

# ---------------- Flask App ----------------
app = Flask(__name__)

# ---------------- Database setup ----------------
# Ensure instance folder exists and is writable
instance_path = os.path.join(os.getcwd(), "instance")
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, "jec.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SECRET_KEY"] = "secret"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

# ---------------- Login ----------------
login_manager = LoginManager(app)
login_manager.login_view = "login"

# ---------------- Models ----------------
class Student(UserMixin, db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100))
    branch = db.Column(db.String(100))
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default="student")
    result = db.Column(db.String(50))
    subject = db.Column(db.String(100))
    attendance_records = db.relationship("Attendance", backref="student", lazy=True)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=db.func.current_timestamp())

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey("student.id"))
    date = db.Column(db.Date, default=db.func.current_date())
    status = db.Column(db.String(10))
    subject = db.Column(db.String(100))

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Utility ----------------
def calculate_attendance_percentage(student_id, month=None, year=None, semester=None):
    query = Attendance.query.filter_by(student_id=student_id)
    if month and year:
        query = query.filter(extract("month", Attendance.date) == month,
                             extract("year", Attendance.date) == year)
    if semester == "Jan-Jun":
        query = query.filter(extract("month", Attendance.date).between(1, 6))
    elif semester == "Jul-Dec":
        query = query.filter(extract("month", Attendance.date).between(7, 12))

    records = query.all()
    if not records:
        return 0
    total = len(records)
    present = sum(1 for r in records if r.status and r.status.lower() == "present")
    return (present / total) * 100

# ---------------- Routes ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        reg = request.form["username"]
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

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        reg = request.form["reg"]
        name = request.form["name"]
        branch = request.form["branch"]
        password = request.form["password"]

        if Student.query.get(reg):
            flash("Registration number already exists", "danger")
            return render_template("register.html")

        new_student = Student(
            id=reg, name=name, branch=branch, password=password,
            role="student", result="Not Available"
        )
        db.session.add(new_student)
        db.session.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# ---------------- Student Dashboard ----------------
@app.route("/student")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return "Access denied"
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    student = Student.query.get(current_user.id)
    attendance_records = Attendance.query.filter_by(student_id=student.id).all()
    files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()

    percent = calculate_attendance_percentage(student.id)
    eligible = "Eligible for Exam" if percent >= 60 else "Not Eligible for Exam"

    return render_template("student.html", student=student, notices=notices,
                           attendance=attendance_records, files=files,
                           percent=percent, eligible=eligible)

# ---------------- Student Monthly Attendance ----------------
@app.route("/student/monthly_attendance", methods=["GET", "POST"])
@login_required
def student_attendance():
    if current_user.role != "student":
        return "Access denied"

    student = Student.query.get(current_user.id)
    attendance_records = Attendance.query.filter_by(student_id=student.id).all()

    month = None
    year = None
    percent = None
    eligible = None

    if request.method == "POST":
        month = int(request.form["month"])
        year = int(request.form["year"])
        filtered_records = [r for r in attendance_records if r.date.month == month and r.date.year == year]

        percent = calculate_attendance_percentage(student.id, month=month, year=year)
        eligible = "Eligible for Exam" if percent >= 60 else "Not Eligible for Exam"

        return render_template(
            "monthly_attendance.html",
            student=student,
            attendance=filtered_records,
            month=month,
            year=year,
            percent=percent,
            eligible=eligible
        )

    return render_template("monthly_attendance.html", student=student, attendance=attendance_records)

# ---------------- Student Semester Attendance ----------------
@app.route("/student/semester_attendance", methods=["GET", "POST"])
@login_required
def semester_attendance():
    if current_user.role != "student":
        return "Access denied"

    student = Student.query.get(current_user.id)
    attendance_records = Attendance.query.filter_by(student_id=student.id).all()

    semester = None
    percent = None
    eligible = None

    if request.method == "POST":
        semester = request.form["semester"]
        percent = calculate_attendance_percentage(student.id, semester=semester)
        eligible = "Eligible for Exam" if percent >= 60 else "Not Eligible for Exam"

        return render_template(
            "semester_attendance.html",
            student=student,
            attendance=attendance_records,
            semester=semester,
            percent=percent,
            eligible=eligible
        )

    return render_template("semester_attendance.html", student=student, attendance=attendance_records)

# ---------------- Admin Dashboard ----------------
@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return "Access denied"
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    students = Student.query.filter(Student.role == "student").all()
    files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
    student_data = []
    for s in students:
        percent = calculate_attendance_percentage(s.id)
        eligible = "Eligible" if percent >= 60 else "Not Eligible"
        student_data.append({"student": s, "percent": percent, "eligible": eligible})
    return render_template("admin.html", notices=notices, students=student_data, files=files)

# ---------------- Reset DB ----------------
@app.route("/reset_db")
def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
    return "Database reset successfully!"

# ---------------- Initialize DB ----------------
with app.app_context():
    db.create_all()
    if not Student.query.get("admin"):
        db.session.add(Student(
            id="admin",
            name="Administrator",
            password="admin123",
            role="admin"
        ))
    if not Notice.query.first():
        db.session.add(Notice(
            title="Upcoming Internal 1 Exam",
            content="Internal 1 for 2nd Semester will be held from 24th March to 26th March."
        ))
    db.session.commit()

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
