from flask import Blueprint, render_template
from flask_login import login_required

from gaminghub.utils.decorators import admin_required

admin = Blueprint("admin", __name__)


@admin.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")