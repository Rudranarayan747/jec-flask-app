import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

# ---------------- Config ----------------
base_dir = os.path.abspath(os.path.dirname(__file__))
instance_dir = os.path.join(base_dir, "instance")
os.makedirs(instance_dir, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(instance_dir, 'jec.db')}"
app.config["SECRET_KEY"] = "secret"

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

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), db.ForeignKey("student.id"))
    date = db.Column(db.Date)
    subject = db.Column(db.String(100))
    period = db.Column(db.Integer)
    status = db.Column(db.String(10))

    __table_args__ = (
        db.UniqueConstraint('student_id', 'date', 'period', name='unique_attendance'),
    )

class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch = db.Column(db.String(50))
    section = db.Column(db.String(10))
    day = db.Column(db.String(20))
    period = db.Column(db.Integer)
    subject = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return Student.query.get(user_id)

# ---------------- Utils ----------------
def calc_percent(student_id):
    records = Attendance.query.filter_by(student_id=student_id).all()
    total = len([r for r in records if r.status in ["Present", "Absent"]])
    present = len([r for r in records if r.status == "Present"])
    return (present / total * 100) if total else 0

# ---------------- Routes ----------------
@app.route("/", methods=["GET","POST"])
def attendance_dashboard():
    branch = request.form.get("branch", "CSE")
    section = request.form.get("section", "A")
    date_str = request.form.get("date", datetime.today().strftime("%Y-%m-%d"))

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    day_name = date_obj.strftime("%A")

    students = Student.query.filter_by(branch=branch, section=section).all()
    timetable = Timetable.query.filter_by(branch=branch, section=section, day=day_name).order_by(Timetable.period).all()

    # % calculation
    overall = []
    for s in students:
        percent = calc_percent(s.id)
        overall.append({
            "percent": percent,
            "eligible": "Eligible" if percent >= 60 else "Low"
        })

    # subject summary
    subject_summary = []
    for p in timetable:
        subject_summary.append({
            "period": p.period,
            "subject": p.subject,
            "present": Attendance.query.filter_by(date=date_obj, period=p.period, status="Present").count(),
            "absent": Attendance.query.filter_by(date=date_obj, period=p.period, status="Absent").count(),
            "off": Attendance.query.filter_by(date=date_obj, period=p.period, status="Off").count()
        })

    return render_template("attendance.html",
        students=students,
        timetable=timetable,
        overall_summary=overall,
        subject_summary=subject_summary,
        selected_branch=branch,
        selected_section=section,
        selected_date=date_str
    )

# ---------------- Submit ----------------
@app.route("/submit", methods=["POST"])
def submit():
    date_obj = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
    branch = request.form["branch"]
    section = request.form["section"]
    day_name = date_obj.strftime("%A")

    students = Student.query.filter_by(branch=branch, section=section).all()
    timetable = Timetable.query.filter_by(branch=branch, section=section, day=day_name).all()

    for s in students:
        for p in timetable:
            status = request.form.get(f"status_{s.id}_{p.id}", "Off")

            existing = Attendance.query.filter_by(
                student_id=s.id,
                date=date_obj,
                period=p.period
            ).first()

            if existing:
                existing.status = status
            else:
                db.session.add(Attendance(
                    student_id=s.id,
                    date=date_obj,
                    subject=p.subject,
                    period=p.period,
                    status=status
                ))

    db.session.commit()
    return redirect("/")

# ---------------- Init ----------------
with app.app_context():
    db.create_all()

    if not Student.query.first():
        db.session.add_all([
            Student(id="101", name="Alok", branch="CSE", section="A", password="123"),
            Student(id="102", name="Subhransu", branch="CSE", section="A", password="123")
        ])

    if not Timetable.query.first():
        db.session.add_all([
            Timetable(branch="CSE", section="A", day="Monday", period=1, subject="MATH"),
            Timetable(branch="CSE", section="A", day="Monday", period=2, subject="CHEM"),
            Timetable(branch="CSE", section="A", day="Monday", period=3, subject="PHY")
        ])

    db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
