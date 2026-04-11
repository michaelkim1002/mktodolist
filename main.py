from datetime import datetime, date, time, timezone
from dotenv import load_dotenv
from email.message import EmailMessage
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from forms import CreateTaskForm, RegisterForm, LoginForm, ContactForm, NewPasswordForm
from random import randint
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, Boolean, Date, Time, func
from sqlalchemy.exc import OperationalError
from werkzeug.security import generate_password_hash, check_password_hash
from zoneinfo import ZoneInfo
import os
import smtplib
import threading
import time as time_module
import pytz

local_tz = ZoneInfo("America/Chicago")
verification_codes = {}
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "fallback_key")
Bootstrap5(app)
ckeditor = CKEditor(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class Base(DeclarativeBase):
    pass
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///tasks.db"
)
db = SQLAlchemy(model_class=Base)
db.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    tasks = relationship("Task", back_populates="user")

class Task(db.Model):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer,db.ForeignKey("users.id"), nullable=False)

    task: Mapped[str] = mapped_column(String(250), nullable=False)
    additional_info: Mapped[str] = mapped_column(String(250), nullable=True)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_time: Mapped[datetime.time] = mapped_column(Time, nullable=True)
    is_finished: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="tasks")

try:
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")
except OperationalError as e:
    print("Database connection failed:", e)
except Exception as e:
    print("Unexpected DB error:", e)
def get_local_now():
    return datetime.now(local_tz).replace(second=0, microsecond=0)
def send_email(to_email, subject, body):
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as connection:
            connection.starttls()
            connection.login(
                user=os.environ.get("ADMIN_EMAIL"),
                password=os.environ.get("ADMIN_EMAIL_PASSWORD")
            )
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = os.environ.get("ADMIN_EMAIL")
            msg["To"] = to_email
            msg.set_content(body)
            connection.send_message(msg)
        print(f"[send_email_async] Sent email to {to_email}")
    except Exception as e:
        print(f"[send_email] General error for {to_email}: {e}")
def check_late_tasks():
    print("[check_late_tasks] Thread started")
    with app.app_context():
        while True:
            try:
                now = get_local_now()
                print(f"[check_late_tasks] now: {now} (tzinfo={now.tzinfo})")

                # Fetch all unfinished, unnotified tasks
                tasks = db.session.execute(
                    db.select(Task).where(
                        Task.is_finished == False,
                        Task.notified == False
                    )
                ).scalars().all()

                for task in tasks:
                    due_time = task.due_time or time(0, 0)
                    naive_due_datetime = datetime.combine(task.due_date, due_time)
                    due_datetime = naive_due_datetime.replace(tzinfo=local_tz)

                    print(f"[check_late_tasks] task due_datetime: {due_datetime} (tzinfo={due_datetime.tzinfo})")
                    print(f"[check_late_tasks] due_datetime <= now? {due_datetime <= now}")

                    if due_datetime <= now:
                        user = db.session.get(User, task.user_id)
                        subject = f"Task Overdue: {task.task}"
                        due_time_str = task.due_time.strftime('%I:%M %p') if task.due_time else "No specific time"
                        body = (
                            f"Hi {user.username},\n\n"
                            f"The following task is now overdue:\n\n"
                            f"Task: {task.task}\n"
                            f"Due: {task.due_date.strftime('%B %d, %Y')} at {due_time_str}\n\n"
                            f"Please log in to update or complete it.\n\n"
                            f"- MKTodoList"
                        )
                        send_email(user.email, subject, body)
                        task.notified = True


                db.session.commit()

            except Exception as e:
                print("Error in check_late_tasks:", e)
                db.session.rollback()

            time_module.sleep(15)

@app.route('/', methods=["GET"])
def show_tasks():
    if current_user.is_authenticated:
        result = db.session.execute(db.select(Task).where(Task.user_id == current_user.id).order_by(Task.due_date.asc(), Task.due_time.asc()))
        tasks = result.scalars().all()
    else:
        tasks = []
    local_tz = pytz.timezone("US/Central")
    now = get_local_now()
    form = CreateTaskForm()
    return render_template("index.html", all_tasks=tasks, current_date=now.strftime("%B %d, %Y"), current_time=now.strftime("%I:%M:%S %p"), form=form, current_user=current_user, today=now.date(), now_time=now.time())

@app.route('/add-task', methods=["POST"])
def add_task():
    form = CreateTaskForm()
    if not current_user.is_authenticated:
        flash("You need to be signed in to do this", category="warning")
        return redirect(url_for("login"))

    if form.validate_on_submit():
        now = get_local_now()
        due_date = form.due_date.data
        due_time = form.due_time.data or time(0, 0)

        if not due_date:
            flash("Please select a due date.", category="warning")
            return redirect(url_for("show_tasks"))

        naive_due_datetime = datetime.combine(due_date, due_time)
        due_datetime = naive_due_datetime.replace(tzinfo=local_tz)

        print(f"[add_task] now: {now} (tzinfo={now.tzinfo})")
        print(f"[add_task] due_datetime: {due_datetime} (tzinfo={due_datetime.tzinfo})")
        print(f"[add_task] due_datetime <= now? {due_datetime <= now}")

        if due_datetime <= now:
            flash("Please choose a due date and time in the future.", category="warning")
            return redirect(url_for("show_tasks"))

        new_task = Task(
            task=form.task.data,
            due_date=due_date,
            due_time=due_time,
            additional_info=form.additional_info.data,
            user_id=current_user.id,
            is_finished=False
        )
        try:
            db.session.add(new_task)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", category="error")
            return redirect(url_for("show_tasks"))

        return redirect(url_for("show_tasks"))

    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", category="warning")

    now = get_local_now()
    result = db.session.execute(db.select(Task).where(Task.user_id == current_user.id).order_by(Task.due_date.asc()))
    tasks = result.scalars().all()
    return render_template(
        "index.html",
        all_tasks=tasks,
        current_date=now.strftime("%B %d, %Y"),
        current_time=now.strftime("%I:%M:%S %p"),
        form=form,
        current_user=current_user,
        today=now.date(),
        now_time=now.time()
    )

@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        results = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = results.scalar()
        if user:
            flash("Email already exists. Log In", category="error")
            return redirect(url_for("login"))

        hash_salt_password = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
        user_email = form.email.data

        new_user = User(
            username=form.username.data,
            email=user_email,
            password=hash_salt_password
        )
        db.session.add(new_user)
        db.session.commit()

        subject = "Welcome to MKTodoList"
        body = (
            f"Welcome, {form.username.data}!\n\n"
            f"Thanks for signing up for MKTodoList, a handy website to help you maintain your everyday tasks.\n\n"
            f"Best,\nMKTodoList"
        )
        send_email(user_email, subject, body)
        login_user(new_user)
        return redirect(url_for("show_tasks"))

    elif request.method == "POST":
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", category="error")

    return render_template("register.html", form=form, current_user=current_user)

@app.route('/reset_password', methods=["GET", "POST"])
def reset_password():
    form = NewPasswordForm()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "send_code":
            email = form.email.data
            if email:
                code = str(randint(100000, 999999))
                verification_codes[email] = code

                send_email(
                    to_email=email,
                    subject="Your Verification Code",
                    body=f"Your verification code is: {code}"
                )
                flash("Verification code sent!", "success")
            else:
                flash("Please enter a valid email address.", "error")
            return redirect(url_for("reset_password"))

        elif action == "reset_password":
            if form.validate_on_submit():
                email = form.email.data
                code = form.verification_code.data
                new_password = form.new_password.data

                if verification_codes.get(email) != code:
                    flash("Invalid verification code.", "error")
                else:
                    user = db.session.execute(db.select(User).where(User.email == email)).scalar()
                    if user:
                        user.password = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=8)
                        db.session.commit()
                        flash("Password reset successful!", "success")
                        verification_codes.pop(email, None)
                        return redirect(url_for("login"))
                    else:
                        flash("User not found.", "error")
            else:
                pass
    return render_template("new_password.html", form=form)

@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        email = form.email.data
        results = db.session.execute(db.select(User).where(User.email == email))
        user = results.scalar()
        if not user:
            flash("Email does not exist")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, password):
            flash("Incorrect Password")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for("show_tasks"))
    elif request.method == "POST":
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{error}", category="error")
    return render_template("login.html", form=form, current_user=current_user)

@app.route('/complete/<int:task_id>', methods=['POST'])
def complete_task(task_id):
    if not current_user.is_authenticated:
        flash("You need to be signed in to complete a task")
        return redirect(url_for("login"))
    task = db.get_or_404(Task, task_id)
    if task.user_id != current_user.id:
        return redirect(url_for("show_tasks"))
    task.is_finished = not task.is_finished
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
    return redirect(url_for('show_tasks'))

@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    if not current_user.is_authenticated:
        flash("You need to be signed in to delete a task")
        return redirect(url_for("login"))
    post_to_delete = db.get_or_404(Task, task_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('show_tasks'))

@app.route('/contact', methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        subject = form.subject.data
        message = form.message.data

        admin_email = os.environ.get("ADMIN_EMAIL")
        if not admin_email:
            flash("Admin email is not configured.", category="error")
            return redirect(url_for("contact"))

        # Send asynchronously using your existing send_email function
        send_email(
            to_email=admin_email,
            subject=f"New Feedback: {subject}",
            body=f"Message from user {current_user.username if current_user.is_authenticated else 'Anonymous'}:\n\n{message}"
        )

        flash("Message Sent! Thank you for your feedback.", category="success")
        return redirect(url_for("contact"))

    return render_template("contact.html", form=form, current_user=current_user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('show_tasks'))
def start_background_tasks():
    with app.app_context():
        threading.Thread(target=check_late_tasks, daemon=True).start()

start_background_tasks()
if __name__ == "__main__":
     app.run(debug=False, port=5001)
