
Database migration: add ``User.is_admin`` and install Flask-Admin
=====================================================================

Purpose
-------

This document describes the migration that separates project-team access from
administrative access.

Existing field:

.. code-block:: python

   project_team = db.Column(db.Boolean, index=True, default=False)

New field:

.. code-block:: python

   is_admin = db.Column(db.Boolean, index=True, default=False, nullable=False)

Semantics
---------

+----------------+----------------------------------------------------------+
| Field          | Meaning                                                  |
+================+==========================================================+
| ``project_team`` | User has project-team access inside the application.   |
+----------------+----------------------------------------------------------+
| ``is_admin``     | User may access Flask-Admin and administer accounts.    |
+----------------+----------------------------------------------------------+

Important: ``project_team=True`` must not automatically imply
``is_admin=True``.

1. Prepare a local test database from the production copy
--------------------------------------------------------

The notebook development database may not contain users. For realistic testing,
copy the existing SQLite database and test the migration against that copy.

On the server, create a copy of the database. If the application is running,
prefer SQLite's backup command:

.. code-block:: bash

   sqlite3 app.db ".backup 'app.db.export-copy.db'"

If the application is stopped, a normal copy is acceptable:

.. code-block:: bash

   cp app.db app.db.export-copy.db

Transfer the copied database to the notebook, for example:

.. code-block:: bash

   scp scp user@server:~/formulae-capitains-nemo/app.db.export-copy ~/git/formulae-capitains-nemo/app.db.export-copy.db

Make sure database files are not tracked by Git:

.. code-block:: bash

   grep -E "app\.db|\*\.db|\*\.sqlite" .gitignore
   git ls-files app.db

Recommended ``.gitignore`` entries:

.. code-block:: text

   app.db
   *.db
   *.sqlite
   *.sqlite3
   *.db-journal
   *.db-wal
   *.db-shm

2. Install SQLite command-line tools if needed
---------------------------------------------

The Flask application can use SQLite without the ``sqlite3`` command-line tool,
but the CLI is useful for inspection and backup.

.. code-block:: bash

   sudo apt install sqlite3

Verify the copied database:

.. code-block:: bash

   sqlite3 app.db.export-copy.db ".tables"
   sqlite3 app.db.export-copy.db ".schema user"

The schema before the migration should not contain ``is_admin``.

3. Use the copied database locally
----------------------------------

Replace the local test database with the copied database:

.. code-block:: bash

   cp app.db.export-copy.db app.db
   sqlite3 app.db "DROP TABLE IF EXISTS _alembic_tmp_user;"

Confirm that Flask uses the expected file:

.. code-block:: python

   from pathlib import Path
   from formulae import create_app

   app = create_app()

   with app.app_context():
       uri = app.config["SQLALCHEMY_DATABASE_URI"]
       print(uri)
       if uri.startswith("sqlite:///"):
           raw_path = uri.replace("sqlite:///", "", 1)
           print(Path(raw_path).resolve())

4. Change the ``User`` model
----------------------------

Add ``is_admin`` next to ``project_team``.

.. code-block:: python

   class User(UserMixin, db.Model):
       id = db.Column(db.Integer, primary_key=True)
       username = db.Column(db.String(64), index=True, unique=True)
       email = db.Column(db.String(120), index=True, unique=True)
       password_hash = db.Column(db.String(128))

       project_team = db.Column(db.Boolean, index=True, default=False)
       is_admin = db.Column(db.Boolean, index=True, default=False, nullable=False)

       default_locale = db.Column(db.String(32), index=True, default="de")
       pages = db.relationship('SavedPage', backref='author', lazy='dynamic')

       def __repr__(self) -> str:
           return '<User {}>'.format(self.username)

       def set_password(self, password: str):
           self.password_hash = generate_password_hash(password)

       def check_password(self, password: str) -> bool:
           return check_password_hash(self.password_hash, password)

In project documentation, the current model can also be embedded directly:

.. code-block:: rst

   .. literalinclude:: ../../formulae/models.py
      :language: python
      :pyobject: User
      :dedent:
      :caption: User model

5. Generate the migration
-------------------------

Run:

.. code-block:: bash

   flask db migrate -m "add is_admin flag to users"

This creates a new file in ``migrations/versions/``. The previous head was
``8e1e2fd2031a``; the new migration should have that revision as its
``down_revision``.

Check:

.. code-block:: bash

   flask db heads
   ls -lh migrations/versions/

6. Edit the generated migration for SQLite
------------------------------------------

Alembic autogenerate may create a direct ``nullable=False`` column addition.
That fails on non-empty SQLite tables with:

.. code-block:: text

   sqlite3.OperationalError: Cannot add a NOT NULL column with default value NULL

Use the safe three-step migration:

1. add the column as nullable,
2. fill existing rows with ``0`` / ``False``,
3. enforce ``NOT NULL``.

Keep the generated ``revision`` and ``down_revision`` values, but edit
``upgrade()`` and ``downgrade()`` like this:

.. code-block:: python

   from alembic import op
   import sqlalchemy as sa


   def upgrade():
       # 1. Add column as nullable first.
       with op.batch_alter_table('user', schema=None) as batch_op:
           batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=True))
           batch_op.create_index(
               batch_op.f('ix_user_is_admin'),
               ['is_admin'],
               unique=False,
           )

       # 2. Fill existing rows. SQLite stores booleans as 0/1.
       op.execute("UPDATE user SET is_admin = 0 WHERE is_admin IS NULL")

       # 3. Now enforce NOT NULL.
       with op.batch_alter_table('user', schema=None) as batch_op:
           batch_op.alter_column(
               'is_admin',
               existing_type=sa.Boolean(),
               nullable=False,
           )


   def downgrade():
       with op.batch_alter_table('user', schema=None) as batch_op:
           batch_op.drop_index(batch_op.f('ix_user_is_admin'))
           batch_op.drop_column('is_admin')

Why use ``0`` instead of ``False``? SQLite stores booleans as integer-like
values, so ``0`` is the safest representation for ``False`` in this migration.

7. Apply and verify locally
---------------------------

Restore a clean copy before re-testing the migration:

.. code-block:: bash

   cp app.db.export-copy.db app.db
   sqlite3 app.db "DROP TABLE IF EXISTS _alembic_tmp_user;"
   flask db upgrade

Verify the schema:

.. code-block:: bash

   sqlite3 app.db "PRAGMA table_info(user);"

Expected row:

.. code-block:: text

   6|is_admin|BOOLEAN|1||0

The ``1`` means ``NOT NULL``.

Verify values:

.. code-block:: bash

   sqlite3 app.db "SELECT id, username, project_team, is_admin FROM user ORDER BY id LIMIT 30;"

Expected: all existing users have ``is_admin = 0``.

8. Promote one local admin user
-------------------------------

Via Python:

.. code-block:: python

   from formulae import create_app, db
   from formulae.models import User

   app = create_app()
   app.app_context().push()

   admin_user = User.query.get(int(<YOUR_USER_ID>))
   admin_user.is_admin = True
   db.session.commit()

Or via SQLite:

.. code-block:: bash

   sqlite3 app.db "SELECT id, username, email, project_team, is_admin FROM user ORDER BY id;"
   sqlite3 app.db "UPDATE user SET is_admin = 1 WHERE id = <YOUR_USER_ID>;"
   sqlite3 app.db "SELECT id, username, email, project_team, is_admin FROM user WHERE id = <YOUR_USER_ID>;"

9. Install Flask-Admin in the correct runtime environment
---------------------------------------------------------

On the dev server, do not rely on plain ``pip``. Install into the environment
used by Supervisor.

For the Formulae application, the relevant environment was:

.. code-block:: bash

   /home/ubuntu/env/bin/python -m pip install Flask-Admin
   /home/ubuntu/env/bin/python -m pip show Flask-Admin

Using plain ``pip install Flask-Admin`` may install into another user or system
environment and still leave the Supervisor-managed application unable to import
``flask_admin``.

10. Create the Flask-Admin module
---------------------------------

Create ``formulae/admin.py``:

.. code-block:: python

   from __future__ import annotations

   from flask import flash, redirect, request, url_for
   from flask_admin import Admin, AdminIndexView
   from flask_admin.contrib.sqla import ModelView
   from flask_login import current_user
   from wtforms import PasswordField
   from wtforms.validators import Length, Optional

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
           return redirect(url_for("auth.r_login", next=request.url))


   class SecureModelView(ModelView):
       def is_accessible(self) -> bool:
           return user_is_admin()

       def inaccessible_callback(self, name, **kwargs):
           flash("You do not have permission to access the administration area.")
           return redirect(url_for("auth.r_login", next=request.url))


   class UserAdminView(SecureModelView):
       column_list = [
           "id",
           "username",
           "email",
           "project_team",
           "is_admin",
           "default_locale",
       ]

       column_searchable_list = ["username", "email"]
       column_filters = ["project_team", "is_admin", "default_locale"]
       column_sortable_list = [
           "id",
           "username",
           "email",
           "project_team",
           "is_admin",
           "default_locale",
       ]

       column_editable_list = ["project_team"]

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
               validators=[Optional(), Length(min=8)],
           )
       }

       form_excluded_columns = ["password_hash", "pages"]
       column_exclude_list = ["password_hash"]

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
       page_size = 50

       def on_model_change(self, form, model: User, is_created: bool):
           if not is_created and model.id == current_user.id:
               if hasattr(form, "is_admin") and not form.is_admin.data:
                   raise ValueError("You cannot remove your own administrator rights.")

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
       name="Formulae Administration",
       template_mode="bootstrap4",
       index_view=SecureAdminIndexView(url="/admin"),
   )

   admin.add_view(
       UserAdminView(
           User,
           db.session,
           name="Users",
           endpoint="admin_users",
       )
   )

11. Register Flask-Admin in the app factory
-------------------------------------------

Inside ``create_app()``:

.. code-block:: python

   from formulae.admin import admin
   admin.init_app(app)

Place this after the main extensions have been initialized.

12. Add the navigation link
---------------------------

In ``navbar.html``, add the administration link inside the logged-in user
dropdown:

.. code-block:: jinja

   {% if current_user.is_admin|default(false) %}
   <div class="dropdown-divider"></div>
   <a class="dropdown-item" href="{{ url_for('admin.index') }}">
       {{ _('Administration') }}
   </a>
   {% endif %}

13. Dev-server rollout
----------------------

Use this order:

.. code-block:: bash

   # Stop the application or ensure no writes to app.db.
   sudo supervisorctl stop formulae-nemo

   # Back up SQLite database.
   cp app.db "app.db.bak-before-is-admin-$(date +%Y%m%d-%H%M%S)"
   ls -lh app.db app.db.bak-before-is-admin-*

   # Pull code and install dependency into the correct environment.
   git pull
   /home/ubuntu/env/bin/python -m pip install Flask-Admin
   /home/ubuntu/env/bin/python -m pip show Flask-Admin

   # Run migration.
   sqlite3 app.db "DROP TABLE IF EXISTS _alembic_tmp_user;"
   flask db upgrade

   # Verify schema and data.
   sqlite3 app.db "PRAGMA table_info(user);"
   sqlite3 app.db "SELECT id, username, project_team, is_admin FROM user ORDER BY id LIMIT 30;"

   # Promote one admin user.
   sqlite3 app.db "UPDATE user SET is_admin = 1 WHERE id = <YOUR_USER_ID>;"
   sqlite3 app.db "SELECT id, username, email, project_team, is_admin FROM user WHERE id = <YOUR_USER_ID>;"

   # Restart only the affected Supervisor service.
   sudo supervisorctl start formulae-nemo
   sudo supervisorctl status formulae-nemo

Prefer ``restart formulae-nemo`` over ``reload``. ``reload`` restarts the
Supervisor daemon and all managed programs and may expose unrelated broken
virtual environments.

14. Verification after deployment
---------------------------------

Check service status:

.. code-block:: bash

   sudo supervisorctl status
   sudo supervisorctl tail -100 formulae-nemo stderr

Test in the browser:

+--------------------------------------+-----------------------------+
| Test                                 | Expected result             |
+======================================+=============================+
| Admin user opens ``/admin``          | Access allowed              |
+--------------------------------------+-----------------------------+
| Admin sees account dropdown link     | ``Administration`` visible  |
+--------------------------------------+-----------------------------+
| Project-team non-admin opens admin   | Access denied / redirected  |
+--------------------------------------+-----------------------------+
| Normal user opens admin              | Access denied / redirected  |
+--------------------------------------+-----------------------------+
| Anonymous user opens admin           | Redirected to login         |
+--------------------------------------+-----------------------------+
| Admin toggles ``project_team``       | Works                       |
+--------------------------------------+-----------------------------+
| Delete user                          | Not available               |
+--------------------------------------+-----------------------------+

15. Rollback
------------

If the deployment fails:

.. code-block:: bash

   sudo supervisorctl stop formulae-nemo
   cp app.db.bak-before-is-admin-YYYYMMDD-HHMMSS app.db
   git checkout <previous-good-commit>
   sudo supervisorctl start formulae-nemo

If the database and Alembic version table get out of sync during local testing,
restore the clean copied DB and rerun the migration instead of manually editing
the schema.
