import click
from flask import Flask

from gaminghub.database.database import db


def register_cli(app: Flask):

    @app.cli.command("promote-admin")
    @click.argument("username")
    def promote_admin(username):
        """Give USERNAME the admin role. For bootstrapping the first
        administrator, when no one can do it through the admin panel yet.
        Recorded in the audit log with no actor (it came from the shell)."""

        from gaminghub.models.user import User
        from gaminghub.services import audit_service

        user = User.query.filter_by(username=username).first()

        if user is None:
            raise click.ClickException(f"No user named {username!r}.")

        if user.role == "admin":
            click.echo(f"{username} is already an admin.")
            return

        old_role = user.role
        user.role = "admin"
        audit_service.record(
            "user_role_changed", target=user, reason="promote-admin CLI", commit=False,
            details={"from": old_role, "to": "admin"}
        )
        db.session.commit()

        click.echo(f"{username} is now an admin.")
