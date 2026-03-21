from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from models import db, Student, Notice, Admin
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jec.db'  # replace with PostgreSQL later
app.config['SECRET_KEY'] = 'secretkey'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return Student.query.filter_by(reg_no=user_id).first() or Admin.query.filter_by(username=user_id).first()

# ---------------- STUDENT FEATURES ----------------
@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if isinstance(current_user, Student):
        notices = Notice.query.all()
        return render_template("student_dashboard.html", student=current_user, notices=notices)
    return redirect(url_for("admin_dashboard"))

@app.route("/student/profile", methods=["GET", "POST"])
@login_required
def student_profile():
    if isinstance(current_user, Student):
        if request.method == "POST":
            current_user.email = request.form["email"]
            current_user.phone = request.form["phone"]
            db.session.commit()
            return redirect(url_for("student_dashboard"))
        return render_template("student_profile.html", student=current_user)
    return redirect(url_for("admin_dashboard"))

# ---------------- ADMIN FEATURES ----------------
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if isinstance(current_user, Admin):
        return render_template("admin_dashboard.html")
    return redirect(url_for("student_dashboard"))

@app.route("/admin/manage_students")
@login_required
def manage_students():
    if isinstance(current_user, Admin):
        students = Student.query.all()
        return render_template("manage_students.html", students=students)
    return redirect(url_for("student_dashboard"))

@app.route("/admin/update_result/<reg>", methods=["GET", "POST"])
@login_required
def update_result(reg):
    if isinstance(current_user, Admin):
        student = Student.query.filter_by(reg_no=reg).first()
        if request.method == "POST":
            student.result = request.form["result"]
            student.attendance = float(request.form["attendance"])
            db.session.commit()
            return redirect(url_for("manage_students"))
        return render_template("update_result.html", student=student)
    return redirect(url_for("student_dashboard"))

@app.route("/admin/add_notice", methods=["GET", "POST"])
@login_required
def add_notice():
    if isinstance(current_user, Admin):
        if request.method == "POST":
            notice = Notice(
                title=request.form["title"],
                content=request.form["content"],
                category=request.form["category"]
            )
            db.session.add(notice)
            db.session.commit()
            return redirect(url_for("admin_dashboard"))
        return render_template("add_notice.html")
    return redirect(url_for("student_dashboard"))
