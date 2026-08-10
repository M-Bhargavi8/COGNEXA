import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user

from gaminghub.database.database import db, bcrypt, limiter
from gaminghub.models.user import User

auth = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not (3 <= len(username) <= 30):
            flash("Username must be between 3 and 30 characters.", "danger")
            return redirect(url_for("auth.register"))

        if not EMAIL_RE.match(email) or len(email) > 120:
            flash("Enter a valid email address.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
            return redirect(url_for("auth.register"))

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")

        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):

            login_user(user)

            flash("Login Successful!", "success")

            return redirect(url_for("dashboard.dashboard_home"))

        flash("Invalid Email or Password", "danger")

    return render_template("login.html")

from flask_login import logout_user

@auth.route("/logout")
def logout():

    logout_user()

    flash("Logged out successfully.", "success")

    return redirect(url_for("main.home"))