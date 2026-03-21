from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------- INITIAL SETUP ----------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jec.db'   # Replace with PostgreSQL later
app.config['SECRET_KEY'] = 'secretkey'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "home"

# ---------------- MODELS ----------------
class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reg_no = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15))
    password = db.Column(db.String(200), nullable=False)  # hashed
    result = db.Column(db.String(50))
    attendance = db.Column(db.Float)

    def get_id(self):
        return self.reg_no

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime)

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

# ---------------- LOGIN MANAGER ----------------
@login_manager.user_loader
def load_user(user_id):
    return Student.query.filter_by(reg_no=user_id).first() or Admin.query.filter_by(username=user_id).first()

# ---------------- ROUTES ----------------
# Home Page
@app.route("/")
def home():
    return render_template("index.html")

# Student Dashboard
@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if isinstance(current_user, Student):
        notices = Notice.query.all()
        return render_template("student_dashboard.html", student=current_user, notices=notices)
    return redirect(url_for("admin_dashboard"))

# Student Profile Update
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

# Admin Dashboard
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    if isinstance(current_user, Admin):
        return render_template("admin_dashboard.html")
    return redirect(url_for("student_dashboard"))

# Manage Students
@app.route("/admin/manage_students")
@login_required
def manage_students():
    if isinstance(current_user, Admin):
        students = Student.query.all()
        return render_template("manage_students.html", students=students)
    return redirect(url_for("student_dashboard"))

# Update Result
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

# Add Notice
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

# ---------------- MAIN ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()   # Ensure database tables are created
    app.run(debug=True)
