from __future__ import annotations

from flask import flash, redirect, request, url_for
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_login import current_user
from wtforms import PasswordField
from wtforms.validators import Length, Optional
from flask_admin.menu import MenuLink
from formulae import db
from formulae.models import User


def user_is_admin() -> bool:
    return (
        current_user.is_authenticated
        and bool(getattr(current_user, "is_admin", False))
    )


class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self) -> bool:
        return user_is_admin()

    def inaccessible_callback(self, name, **kwargs):
        flash("Please log in with an administrator account to access this page.")
        return redirect(url_for("login", next=request.url))


class SecureModelView(ModelView):
    def is_accessible(self) -> bool:
        return user_is_admin()

    def inaccessible_callback(self, name, **kwargs):
        flash("You do not have permission to access the administration area.")
        return redirect(url_for("login", next=request.url))


class UserAdminView(SecureModelView):
    column_list = [
        "id",
        "username",
        "email",
        "project_team",
        "is_admin",
        "default_locale",
    ]

    column_searchable_list = [
        "username",
        "email",
    ]

    column_filters = [
        "project_team",
        "is_admin",
        "default_locale",
    ]

    column_sortable_list = [
        "id",
        "username",
        "email",
        "project_team",
        "is_admin",
        "default_locale",
    ]

    # Convenient for toggling project team membership.
    # Do not add is_admin here; admin changes should be deliberate.
    column_editable_list = [
        "project_team",
    ]

    form_columns = [
        "username",
        "email",
        "project_team",
        "is_admin",
        "default_locale",
        "password",
    ]

    form_extra_fields = {
        "password": PasswordField(
            "New password",
            description=(
                "Leave empty to keep the existing password. "
                "Set a value only to reset the password."
            ),
            validators=[
                Optional(),
                Length(min=8),
            ],
        )
    }

    form_excluded_columns = [
        "password_hash",
        "pages",
    ]

    column_exclude_list = [
        "password_hash",
    ]

    column_labels = {
        "id": "ID",
        "username": "Username",
        "email": "Email",
        "project_team": "Project team",
        "is_admin": "Administrator",
        "default_locale": "Default locale",
    }

    can_create = True
    can_edit = True
    can_delete = False
    can_view_details = True
    page_size = 100

    def on_model_change(self, form, model: User, is_created: bool):
        # Prevent accidental self-lockout.
        if not is_created and model.id == current_user.id:
            if hasattr(form, "is_admin") and not form.is_admin.data:
                raise ValueError(
                    "You cannot remove your own administrator rights."
                )

        password = form.password.data if hasattr(form, "password") else None

        if is_created and not password:
            raise ValueError("A password is required for new users.")

        if password:
            model.set_password(password)

        return super().on_model_change(form, model, is_created)

    def on_model_delete(self, model: User):
        if model.id == current_user.id:
            raise ValueError("You cannot delete your own account.")

        return super().on_model_delete(model)


admin = Admin(
    name="Formulae-Capitains-Nemo Administration",
    index_view=SecureAdminIndexView(url="/admin"),
)

admin.add_link(
        MenuLink(
            name="Back to the Application",
            endpoint="InstanceNemo.r_index",
        )
    )

admin.add_view(
    UserAdminView(
        User,
        db.session,
        name="Users",
        endpoint="admin_users",
    )
)

