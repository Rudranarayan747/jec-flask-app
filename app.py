import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from collections import defaultdict

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
    section = db.Column(db.String(10))
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
    status = db.Column(db.String(10))  # Present, Absent, Off
    subject = db.Column(db.String(100))
    period = db.Column(db.String(50))

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    day = db.Column(db.String(20), nullable=False)
    period = db.Column(db.Integer, nullable=False)
    subject = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Utilities ----------------
def calculate_attendance_percentage(student_id):
    records = Attendance.query.filter_by(student_id=student_id).all()
    if not records:
        return 0
    # Only count Present/Absent, ignore Off
    total = sum(1 for r in records if r.status and r.status.lower() in ["present", "absent"])
    present = sum(1 for r in records if r.status and r.status.lower() == "present")
    return (present / total) * 100 if total > 0 else 0

# ---------------- Routes ----------------
@app.route("/")
def home():
    return render_template("index.html")

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

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        reg = request.form.get("reg")
        name = request.form.get("name")
        branch = request.form.get("branch")
        section = request.form.get("section")
        password = request.form.get("password")

        if Student.query.get(reg):
            flash("Registration number already exists", "danger")
            return render_template("register.html")

        new_student = Student(id=reg, name=name, branch=branch, section=section,
                              password=password, role="student", result="Not Available")
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

    selected_branch = request.form.get("branch", "")
    selected_section = request.form.get("section", "")
    selected_date = request.form.get("date", datetime.today().strftime("%Y-%m-%d"))

    students, timetable, overall_summary = [], [], []
    section_summary = defaultdict(list)
    subject_summary = []  # NEW: subject-wise summary

    if selected_branch and selected_section:
        try:
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format", "danger")
            return redirect(url_for("attendance_dashboard"))

        day_name = date_obj.strftime("%A")
        students = Student.query.filter_by(branch=selected_branch, section=selected_section).order_by(Student.id).all()
        timetable = Timetable.query.filter_by(branch=selected_branch, section=selected_section, day=day_name).order_by(Timetable.period).all()

        # Student overall summary
        for s in students:
            percent = calculate_attendance_percentage(s.id)
            eligible = "Eligible" if percent >= 60 else "Not Eligible"
            overall_summary.append({"student": s, "percent": percent, "eligible": eligible})
            section_summary[s.section].append(percent)

        # Subject-wise summary
        for p in timetable:
            present_count = Attendance.query.filter_by(date=date_obj, subject=p.subject, status="Present").count()
            absent_count = Attendance.query.filter_by(date=date_obj, subject=p.subject, status="Absent").count()
            off_count = Attendance.query.filter_by(date=date_obj, subject=p.subject, status="Off").count()

            subject_summary.append({
                "period": p.period,
                "subject": p.subject,
                "present": present_count,
                "absent": absent_count,
                "off": off_count
            })

    # Section averages
    section_data = []
    for sec, percents in section_summary.items():
        avg = sum(percents) / len(percents) if percents else 0
        section_data.append({"section": sec, "average": avg})

    return render_template("attendance.html",
                           students=students,
                           selected_branch=selected_branch,
                           selected_section=selected_section,
                           selected_date=selected_date,
                           overall_summary=overall_summary,
                           section_data=section_data,
                           timetable=timetable,
                           subject_summary=subject_summary)  # pass to template

  # ---------------- Submit Attendance ----------------
@app.route("/admin/submit_attendance", methods=["POST"])
@login_required
def submit_attendance():
    if current_user.role != "admin":
        return "Access denied"

    date_str = request.form.get("date")
    branch = request.form.get("branch", "").strip()
    section = request.form.get("section", "").strip()
    if not branch or not section:
        flash("Branch and Section are required", "danger")
        return redirect(url_for("attendance_dashboard"))

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format", "danger")
        return redirect(url_for("attendance_dashboard"))

    students = Student.query.filter_by(branch=branch, section=section).all()
    day_name = date_obj.strftime("%A")
    timetable = Timetable.query.filter_by(branch=branch, section=section, day=day_name).all()

    for s in students:
        for p in timetable:
            status = request.form.get(f"status_{s.id}_{p.id}")  # safer to use p.id
            if status in ["Present", "Absent", "Off"]:
                existing = Attendance.query.filter_by(
                    student_id=s.id, date=date_obj, subject=p.subject
                ).first()
                if existing:
                    existing.status = status
                else:
                    att = Attendance(
                        student_id=s.id,
                        date=date_obj,
                        subject=p.subject,
                        period=p.period,
                        status=status
                    )
                    db.session.add(att)

    db.session.commit()
    flash("Attendance recorded successfully!", "success")
    return redirect(url_for("attendance_dashboard"))

# ---------------- Submit Attendance ----------------
@app.route("/admin/submit_attendance", methods=["POST"])
@login_required
def submit_attendance():
    if current_user.role != "admin":
        return "Access denied"

    date_str = request.form.get("date")
    branch = request.form.get("branch", "").strip()
    section = request.form.get("section", "").strip()
    if not branch or not section:
        flash("Branch and Section are required", "danger")
        return redirect(url_for("attendance_dashboard"))

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid date format", "danger")
        return redirect(url_for("attendance_dashboard"))

    students = Student.query.filter_by(branch=branch, section=section).all()
    day_name = date_obj.strftime("%A")
    timetable = Timetable.query.filter_by(branch=branch, section=section, day=day_name).all()

    for s in students:
        for p in timetable:
            # Default to "Off" if nothing selected
            status = request.form.get(f"status_{s.id}_{p.id}", "Off")
            existing = Attendance.query.filter_by(
                student_id=s.id, date=date_obj, subject=p.subject
            ).first()
            if existing:
                existing.status = status
            else:
                att = Attendance(
                    student_id=s.id,
                    date=date_obj,
                    subject=p.subject,
                    period=p.period,
                    status=status
                )
                db.session.add(att)

    db.session.commit()
    flash("Attendance recorded successfully!", "success")
    return redirect(url_for("attendance_dashboard"))

    # ---------------- Update Student ----------------
@app.route("/admin/update_student/<student_id>", methods=["POST"])
@login_required
def update_student(student_id):
    if current_user.role != "admin":
        return "Access denied"

    student = Student.query.get(student_id)
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("admin_dashboard"))

    # Get updated fields from form
    student.name = request.form.get("name")
    student.branch = request.form.get("branch")
    student.password = request.form.get("password")
    student.result = request.form.get("result")

    db.session.commit()
    flash("Student updated successfully!", "success")
    return redirect(url_for("admin_dashboard"))

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

    # Save in static/uploads
    upload_static_dir = os.path.join(app.root_path, "static", "uploads")
    os.makedirs(upload_static_dir, exist_ok=True)
    filepath = os.path.join(upload_static_dir, file.filename)
    file.save(filepath)

    uploaded = UploadedFile(filename=file.filename, filepath=f"uploads/{file.filename}")
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

if __name__ == "__main__":
    app.run(debug=True)
