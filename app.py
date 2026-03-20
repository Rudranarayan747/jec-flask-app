from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///jec.db"
app.config["SECRET_KEY"] = "secret"
db = SQLAlchemy(app)
login_manager = LoginManager(app)

# ---------------- Models ----------------
class Student(UserMixin, db.Model):
    id = db.Column(db.String(50), primary_key=True)  # registration number
    name = db.Column(db.String(100))
    password = db.Column(db.String(100))
    role = db.Column(db.String(20), default="student")
    result = db.Column(db.String(50))

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, default=db.func.current_timestamp())

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Routes ----------------
@app.route("/")
def index():
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
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        reg = request.form["reg"]
        name = request.form["name"]
        password = request.form["password"]

        if Student.query.get(reg):
            return render_template("register.html", error="Registration number already exists")

        new_student = Student(id=reg, name=name, password=password, role="student", result="Not Available")
        db.session.add(new_student)
        db.session.commit()
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/student")
@login_required
def student_dashboard():
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    student = Student.query.get(current_user.id)
    return render_template("student.html", student=student, notices=notices)

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.role != "admin":
        return "Access denied"
    notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    return render_template("admin.html", notices=notices)

@app.route("/admin/add_notice", methods=["GET", "POST"])
@login_required
def add_notice():
    if current_user.role != "admin":
        return "Access denied"
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        notice = Notice(title=title, content=content)
        db.session.add(notice)
        db.session.commit()
        return redirect(url_for("admin_dashboard"))
    return render_template("add_notice.html")

@app.route("/notices")
@login_required
def notices():
    all_notices = Notice.query.order_by(Notice.date_posted.desc()).all()
    return render_template("notices.html", notices=all_notices)

# ---------------- Student Management ----------------
@app.route("/admin/students")
@login_required
def manage_students():
    if current_user.role != "admin":
        return "Access denied"
    students = Student.query.filter(Student.role == "student").all()
    return render_template("manage_students.html", students=students)

@app.route("/admin/update_result/<reg>", methods=["GET", "POST"])
@login_required
def update_result(reg):
    if current_user.role != "admin":
        return "Access denied"
    student = Student.query.get(reg)
    if not student:
        return "Student not found"
    if request.method == "POST":
        new_result = request.form["result"]
        student.result = new_result
        db.session.commit()
        return redirect(url_for("manage_students"))
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
    return redirect(url_for("manage_students"))

# ---------------- Initialize ----------------
with app.app_context():
    db.create_all()
    # Create default admin
    if not Student.query.get("admin"):
        db.session.add(Student(id="admin", name="Administrator", password="admin123", role="admin"))
    # Preload exam notice
    if not Notice.query.first():
        db.session.add(Notice(
            title="Upcoming Internal 1 Exam",
            content="Internal 1 for 2nd Semester will be held from 24th March to 26th March."
        ))
    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

