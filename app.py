from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
import os
from sqlalchemy import extract
from datetime import datetime

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
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default="student")
    result = db.Column(db.String(50))

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
        branch = request.form["branch"]   # ✅ capture branch
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


# ✅ Reset DB route must be at the same level as admin_dashboard
@app.route("/reset_db")
def reset_db():
    with app.app_context():
        db.drop_all()
        db.create_all()
    return "Database reset successfully!"




# ---------------- Update & Delete ----------------
@app.route("/admin/update_student/<reg>", methods=["GET", "POST"])
@login_required
def update_student(reg):
    if current_user.role != "admin":
        return "Access denied"
    student = Student.query.get(reg)
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        new_branch = request.form["branch"]
        new_result = request.form["result"]
        student.branch = new_branch
        student.result = new_result
        db.session.commit()
        flash("Student updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("update_student.html", student=student)

@app.route("/admin/delete_student/<reg>", methods=["GET", "POST"])
@login_required
def delete_student(reg):
    if current_user.role != "admin":
        return "Access denied"
    student = Student.query.get(reg)
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        db.session.delete(student)
        db.session.commit()
        flash("Student deleted successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("delete_student.html", student=student)

# ---------------- Attendance Dashboard ----------------
@app.route("/admin/attendance_dashboard", methods=["GET", "POST"])
@login_required
def attendance_dashboard():
    if current_user.role != "admin":
        return "Access denied"

    students = Student.query.filter(Student.role == "student").all()

    if request.method == "POST":
        date_str = request.form.get("date")
        if date_str:
            chosen_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            chosen_date = datetime.today().date()

        for student in students:
            status = request.form.get(f"status_{student.id}")
            if status:
                record = Attendance(student_id=student.id, status=status, date=chosen_date)
                db.session.add(record)
        db.session.commit()
        flash(f"Attendance submitted for {chosen_date.strftime('%d-%m-%Y')}!", "success")
        return redirect(url_for("attendance_dashboard"))

    summary = []
    for s in students:
        percent = calculate_attendance_percentage(s.id)
        eligible = "Eligible" if percent >= 60 else "Not Eligible"
        summary.append({"student": s, "percent": percent, "eligible": eligible})

    return render_template("attendance_dashboard.html", students=students, summary=summary)

# ---------------- Search Attendance ----------------
@app.route("/admin/search_attendance", methods=["GET", "POST"])
@login_required
def search_attendance():
    if current_user.role != "admin":
        return "Access denied"

    records = None
    branch = None
    month = None

    if request.method == "POST":
        month_str = request.form["month"]  # format: YYYY-MM
        branch = request.form["branch"]
        year, month_num = map(int, month_str.split("-"))

        # Get all attendance records for that month
        records = Attendance.query.filter(
            extract("month", Attendance.date) == month_num,
            extract("year", Attendance.date) == year
        ).all()

        # Filter by branch
        records = [r for r in records if r.student.branch.lower() == branch.lower()]

        month = month_str

    return render_template("search_attendance.html", records=records, branch=branch, month=month)


# Export Monthly Attendance as PDF
@app.route("/admin/export_monthly_pdf")
@login_required
def export_monthly_pdf():
    if current_user.role != "admin":
        return "Access denied"

    month_str = request.args.get("month")
    branch = request.args.get("branch")
    year, month_num = map(int, month_str.split("-"))

    records = Attendance.query.filter(
        extract("month", Attendance.date) == month_num,
        extract("year", Attendance.date) == year
    ).all()
    records = [r for r in records if r.student.branch.lower() == branch.lower()]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, f"Monthly Attendance Report - {branch} ({month_str})", ln=True, align="C")

    pdf.cell(30, 10, "Reg No", 1)
    pdf.cell(50, 10, "Name", 1)
    pdf.cell(30, 10, "Branch", 1)
    pdf.cell(30, 10, "Date", 1)
    pdf.cell(30, 10, "Status", 1)
    pdf.ln()

    for r in records:
        pdf.cell(30, 10, r.student.id, 1)
        pdf.cell(50, 10, r.student.name, 1)
        pdf.cell(30, 10, r.student.branch, 1)
        pdf.cell(30, 10, r.date.strftime("%Y-%m-%d"), 1)
        pdf.cell(30, 10, r.status, 1)
        pdf.ln()

    response = make_response(pdf.output(dest="S").encode("latin1"))
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{branch}_{month_str}.pdf"
    return response


# Export Monthly Attendance as Excel
@app.route("/admin/export_monthly_excel")
@login_required
def export_monthly_excel():
    if current_user.role != "admin":
        return "Access denied"

    month_str = request.args.get("month")
    branch = request.args.get("branch")
    year, month_num = map(int, month_str.split("-"))

    records = Attendance.query.filter(
        extract("month", Attendance.date) == month_num,
        extract("year", Attendance.date) == year
    ).all()
    records = [r for r in records if r.student.branch.lower() == branch.lower()]

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()

    headers = ["Reg No", "Name", "Branch", "Date", "Status"]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)

    for row, r in enumerate(records, start=1):
        worksheet.write(row, 0, r.student.id)
        worksheet.write(row, 1, r.student.name)
        worksheet.write(row, 2, r.student.branch)
        worksheet.write(row, 3, r.date.strftime("%Y-%m-%d"))
        worksheet.write(row, 4, r.status)

    workbook.close()
    output.seek(0)

    response = make_response(output.read())
    response.headers["Content-Disposition"] = f"attachment; filename=attendance_{branch}_{month_str}.xlsx"
    response.headers["Content-Type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

# ---------------- Upload PDF ----------------
@app.route("/upload_pdf", methods=["POST"])
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
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    new_file = UploadedFile(filename=filename, filepath=filepath)
    db.session.add(new_file)
    db.session.commit()
    flash("File uploaded successfully!", "success")
    return redirect(url_for("admin_dashboard"))

# ---------------- Student Monthly/Semester Attendance ----------------
@app.route("/student/monthly_attendance")
@login_required
def student_attendance():
    if current_user.role != "student":
        return "Access denied"
    return render_template("monthly_attendance.html")

@app.route("/student/semester_attendance")
@login_required
def semester_attendance():
    if current_user.role != "student":
        return "Access denied"
    return render_template("semester_attendance.html")

# ---------------- Add Notice ----------------
@app.route("/add_notice", methods=["GET", "POST"])
@login_required
def add_notice():
    if current_user.role != "admin":
        return "Access denied"
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        new_notice = Notice(title=title, content=content)
        db.session.add(new_notice)
        db.session.commit()
        flash("Notice added successfully!", "success")
        return redirect(url_for("admin_dashboard"))
    return render_template("add_notice.html")
    # ---------------- Initialize ----------------
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

 
