from flask import Flask, render_template, request, redirect, url_for, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import os
from sqlalchemy import extract
from datetime import datetime
import io
import xlsxwriter
from fpdf import FPDF

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jec.db"
app.config["SECRET_KEY"] = "secret"
app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
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
    attendance_records = db.relationship("Attendance", backref="student", lazy=True)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=db.func.current_timestamp())

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey("student.id"))
    date = db.Column(db.Date)
    status = db.Column(db.String(10))
    subject = db.Column(db.String(100))

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200))
    filepath = db.Column(db.String(300))
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Utility ----------------
def calculate_attendance_percentage(student_id):
    records = Attendance.query.filter_by(student_id=student_id).all()
    if not records:
        return 0
    total = len(records)
    present = sum(1 for r in records if r.status.lower() == "present")
    return (present / total) * 100

# ---------------- Routes ----------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = Student.query.get(request.form["username"])
        if user and user.password == request.form["password"]:
            login_user(user)
            return redirect(url_for("admin_dashboard") if user.role == "admin" else "student_dashboard")
        flash("Invalid credentials")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if Student.query.get(request.form["reg"]):
            flash("User exists")
            return redirect(url_for("register"))

        student = Student(
            id=request.form["reg"],
            name=request.form["name"],
            branch=request.form["branch"],
            password=request.form["password"]
        )
        db.session.add(student)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/admin")
@login_required
def admin_dashboard():
    students = Student.query.filter_by(role="student").all()
    data = []
    for s in students:
        percent = calculate_attendance_percentage(s.id)
        data.append({"student": s, "percent": percent})
    return render_template("admin.html", students=data)

# ---------------- Attendance Dashboard ----------------
@app.route("/admin/attendance_dashboard", methods=["GET", "POST"])
@login_required
def attendance_dashboard():
    if current_user.role != "admin":
        return "Access denied"

    selected_branch = request.form.get("branch")

    students = Student.query.filter_by(role="student", branch=selected_branch).all() if selected_branch else []

    if request.method == "POST" and request.form.get("date"):
        date = datetime.strptime(request.form.get("date"), "%Y-%m-%d").date()

        for student in students:
            subjects = ["Math", "ETW", "BME", "Chem", "BEE", "EM"] if student.branch.lower() == "cse" else ["PCDS", "Math", "UHV", "BEE", "Phy", "BCE"]

            for subj in subjects:
                status = request.form.get(f"status_{student.id}_{subj}")

                # ✅ Skip OFF
                if status and status != "Off":
                    db.session.add(Attendance(
                        student_id=student.id,
                        subject=subj,
                        status=status,
                        date=date
                    ))

        db.session.commit()
        flash("Attendance submitted")
        return redirect(url_for("attendance_dashboard"))

    # Subject-wise
    summary = []
    for s in students:
        subjects = ["Math", "ETW", "BME", "Chem", "BEE", "EM"] if s.branch.lower() == "cse" else ["PCDS", "Math", "UHV", "BEE", "Phy", "BCE"]

        for subj in subjects:
            rec = Attendance.query.filter_by(student_id=s.id, subject=subj).all()
            total = len(rec)
            present = sum(1 for r in rec if r.status.lower() == "present")
            percent = (present / total * 100) if total else 0

            summary.append({"student": s, "subject": subj, "percent": percent})

    # Overall
    overall_summary = []
    for s in students:
        rec = Attendance.query.filter_by(student_id=s.id).all()
        total = len(rec)
        present = sum(1 for r in rec if r.status.lower() == "present")
        percent = (present / total * 100) if total else 0

        overall_summary.append({"student": s, "percent": percent})

    return render_template("attendance_dashboard.html",
                           students=students,
                           selected_branch=selected_branch,
                           summary=summary,
                           overall_summary=overall_summary)

# ---------------- Initialize ----------------
with app.app_context():
    db.create_all()
    if not Student.query.get("admin"):
        db.session.add(Student(id="admin", name="Admin", password="admin123", role="admin"))
    db.session.commit()

# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
