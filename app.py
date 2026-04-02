import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ---------------- App Config ----------------
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(base_dir, "instance")
upload_dir = os.path.join(instance_dir, "uploads")
os.makedirs(instance_dir, exist_ok=True)
os.makedirs(upload_dir, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_dir, 'jec.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "secret"
app.config["UPLOAD_FOLDER"] = upload_dir

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
    date = db.Column(db.Date, default=db.func.current_date())
    status = db.Column(db.String(10))
    subject = db.Column(db.String(100))
    period = db.Column(db.String(50))  # Timetable period/slot

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Utilities ----------------
def calculate_attendance_percentage(student_id):
    records = Attendance.query.filter_by(student_id=student_id).all()
    if not records:
        return 0
    total = len(records)
    present = sum(1 for r in records if r.status and r.status.lower() == "present")
    return (present / total) * 100

# ---------------- Routes ----------------
@app.route("/")
def home():
    return render_template("index.html")

# ---------------- Login & Logout ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        reg = request.form.get("username")
        password = request.form.get("password")
        user = Student.query.get(reg)
        if user and user.password == password:
            login_user(user)
            return redirect(url_for("admin_dashboard") if user.role == "admin" else url_for("student_dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

# ---------------- Registration ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        reg = request.form.get("reg")
        name = request.form.get("name")
        branch = request.form.get("branch")
        password = request.form.get("password")

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

# ---------------- Student Dashboard ----------------
@app.route("/student")
@login_required
def student_dashboard():
    if current_user.role != "student":
        return "Access denied"
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    student = Student.query.get(current_user.id)
    files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
    percent = calculate_attendance_percentage(student.id)
    eligible = "Eligible for Exam" if percent >= 60 else "Not Eligible for Exam"
    return render_template("student.html", student=student, notices=notices,
                           files=files, percent=percent, eligible=eligible)

# ---------------- Admin Dashboard ----------------
@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return "Access denied"
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    students = Student.query.filter(Student.role == "student").order_by(Student.id).all()
    files = UploadedFile.query.order_by(UploadedFile.uploaded_at.desc()).all()
    student_data = []
    for s in students:
        percent = calculate_attendance_percentage(s.id)
        eligible = "Eligible" if percent >= 60 else "Not Eligible"
        student_data.append({"student": s, "percent": percent, "eligible": eligible})
    return render_template("admin.html", notices=notices, students=student_data, files=files)

# ---------------- Attendance Dashboard ----------------
@app.route("/admin/attendance", methods=["GET", "POST"])
@login_required
def attendance_dashboard():
    if current_user.role != "admin":
        return "Access denied"

    students = []
    selected_branch = ""
    selected_date = datetime.today().strftime("%Y-%m-%d")
    overall_summary = []

    if request.method == "POST":
        selected_branch = request.form.get("branch", "").strip()
        selected_date = request.form.get("date", datetime.today().strftime("%Y-%m-%d"))
        try:
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format", "danger")
            return redirect(url_for("attendance_dashboard"))

        students = Student.query.filter_by(branch=selected_branch).order_by(Student.id).all()

        for s in students:
            percent = calculate_attendance_percentage(s.id)
            eligible = "Eligible" if percent >= 60 else "Not Eligible"
            overall_summary.append({"student": s, "percent": percent, "eligible": eligible})

    return render_template("attendance.html", students=students, selected_branch=selected_branch,
                           selected_date=selected_date, overall_summary=overall_summary)

# ---------------- Submit Attendance ----------------
@app.route("/admin/submit_attendance", methods=["POST"])
@login_required
def submit_attendance():
    if current_user.role != "admin":
        return "Access denied"

    date_str = request.form.get("date")
    branch = request.form.get("branch", "").strip()
    if not branch:
        flash("Branch is required", "danger")
        return redirect(url_for("attendance_dashboard"))

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format", "danger")
        return redirect(url_for("attendance_dashboard"))

    students = Student.query.filter_by(branch=branch).all()

    for s in students:
        subjects = ['Math','ETW','BME','Chem','BEE','EM'] if (s.branch or "").lower() == 'cse' else ['PCDS','Math','UHV','BEE','Phy','BCE']
        for subj in subjects:
            status = request.form.get(f"status_{s.id}_{subj}")
            if status:
                existing = Attendance.query.filter_by(student_id=s.id, date=date_obj, subject=subj).first()
                if existing:
                    existing.status = status
                else:
                    att = Attendance(student_id=s.id, date=date_obj, subject=subj, period=subj, status=status)
                    db.session.add(att)
    db.session.commit()
    flash("Attendance recorded successfully!", "success")
    return redirect(url_for("attendance_dashboard"))

# ---------------- Add Notice ----------------
@app.route("/admin/add_notice", methods=["GET", "POST"])
@login_required
def add_notice():
    if current_user.role != "admin":
        return "Access denied"
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        notice = Notice(title=title, content=content)
        db.session.add(notice)
        db.session.commit()
        flash("Notice added successfully", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("add_notice.html")

# ---------------- Upload PDF ----------------
@app.route("/admin/upload_pdf", methods=["POST"])
@login_required
def upload_pdf():
    if current_user.role != "admin":
        return "Access denied"
    if "pdf" not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for("admin_dashboard"))
    file = request.files["pdf"]
    if file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("admin_dashboard"))
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(filepath)
    uploaded = UploadedFile(filename=file.filename, filepath=filepath)
    db.session.add(uploaded)
    db.session.commit()
    flash("PDF uploaded successfully", "success")
    return redirect(url_for("admin_dashboard"))

# ---------------- Initialize DB ----------------
with app.app_context():
    db.create_all()
    if not Student.query.get("admin"):
        db.session.add(Student(id="admin", name="Administrator", password="admin123", role="admin"))
    if not Notice.query.first():
        db.session.add(Notice(title="Welcome Notice", content="Welcome to the Attendance Management System."))
    db.session.commit()

# ---------------- Run App ----------------
if __name__ == "__main__":
    app.run(debug=True)
