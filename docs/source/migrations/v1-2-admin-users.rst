Version 1.2: Database Migration 
=====================================

This migration belongs to version `1.2` / `v1.2.0`. The change is a minor feature release because it adds a new administrative user interface and a new database column. Before running the migration on a server, make sure that all code changes are
committed and deployed, including:

.. code-block:: text

   formulae/models.py
   formulae/admin.py
   formulae/**init**.py
   formulae/templates/navbar.html
   migrations/versions/<revision>_add_is_admin_flag_to_users.py
   requirements.txt


Do not commit local SQLite database files:

.. code-block:: text

   *.db
   *.sqlite
   *.sqlite3


Model Change
-------------
The `User` model should contain both `project_team` and `is_admin`:

.. code-block:: python

   class User(UserMixin, db.Model):
      ...
      project_team = db.Column(db.Boolean, index=True, default=False)
      is_admin = db.Column(db.Boolean, index=True, default=False, nullable=False)
      ...

Migration File
-------------
The migration must not add `is_admin` immediately as `nullable=False`.
SQLite cannot add a non-nullable column to an existing non-empty table unless a
server-side default is provided.

The safe migration sequence is:

#. Add the column as temporarily nullable.
#. Set all existing `NULL` values to `0`.
#. Change the column to `nullable=False`.

Example migration:

.. code-block:: python

   from alembic import op
   import sqlalchemy as sa

revision identifiers, used by Alembic.
-------------

.. code-block:: python

   revision = "<new_revision_id>"
   down_revision = "<previous_revision_id>"
   branch_labels = None
   depends_on = None

   def upgrade():
      # 1. Add the new column as nullable first.
      with op.batch_alter_table("user", schema=None) as batch_op:
      batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=True))
      batch_op.create_index(
      batch_op.f("ix_user_is_admin"),
      ["is_admin"],
      unique=False,
      )
   
   # 2. Initialize all existing users as non-admin.
   op.execute("UPDATE user SET is_admin = 0 WHERE is_admin IS NULL")

   # 3. Enforce NOT NULL after all rows have a value.
   with op.batch_alter_table("user", schema=None) as batch_op:
       batch_op.alter_column(
           "is_admin",
           existing_type=sa.Boolean(),
           nullable=False,
       )


   def downgrade():
   with op.batch_alter_table("user", schema=None) as batch_op:
   batch_op.drop_index(batch_op.f("ix_user_is_admin"))
   batch_op.drop_column("is_admin")

Generating the Migration
-------------
If the migration file does not exist yet, generate it with:

.. code-block:: bash

   flask db migrate -m "add is_admin flag to users"

Then inspect the generated file in:

.. code-block:: text

   migrations/versions/

Edit the generated migration so that it follows the safe SQLite sequence shown
above.

Checking the Current Migration State
-------------
Before applying the migration, check the available migration head:

.. code-block:: bash

   python -m flask db heads

Example output after the migration has been added:

.. code-block:: text

   <new_revision_id> (head)

Then check the current database revision:

.. code-block:: bash

   python -m flask db current

If the database is still at the previous revision, the migration has not yet
been applied.

Installing Required Python Packages
-------------
Version 1.2 requires Flask-Admin. Install packages into the same Python environment used by the running application. Do not rely on plain `pip` unless you are certain that it points to the correct virtual environment.

Use one of the following patterns:

.. code-block:: bash

   python -m pip install -r requirements.txt

or, if the application uses a virtual environment:

.. code-block:: bash

   <path-to-venv>/bin/python -m pip install -r requirements.txt

Verify the required packages:

.. code-block:: bash

   python -m pip show Flask-Admin
   python -m pip show python-dotenv
   python -m pip show Flask-Migrate

If `Flask-Admin` is missing, the application may fail to start after
deployment.

Migration Procedure
-------------
The following procedure assumes that the application uses SQLite. Adapt the
database filename and process-management commands to the relevant environment.

1. Stop the Application
```

Stop only the application process. Do not restart unrelated services.

Example:

.. code-block:: bash

   supervisorctl stop <application-process-name>

Check the status:

.. code-block:: bash

   supervisorctl status <application-process-name>

2. Back Up the Database
```

Create a timestamped backup before running the migration:

.. code-block:: bash

   cp <database-file> "<database-file>.bak-before-v1.2-$(date +%Y%m%d-%H%M%S)"

Confirm that the backup exists and has a plausible file size:

.. code-block:: bash

   ls -lh <database-file> <database-file>.bak-before-v1.2-*

Alternatively, use SQLite's backup command:

.. code-block:: bash

   sqlite3 <database-file> ".backup '<database-file>.bak-before-v1.2-$(date +%Y%m%d-%H%M%S)'"

Do not continue unless the backup was created successfully.

3. Pull the New Code
```

Deploy the new application code using the normal deployment workflow.

Example:

.. code-block:: bash

   git pull

Check that the new migration file is present:

.. code-block:: bash

   ls -lh migrations/versions/
   python -m flask db heads

4. Install Dependencies
```

Install dependencies into the environment used by the application:

.. code-block:: bash

   python -m pip install -r requirements.txt

If the application uses a virtual environment, call Python from that environment:

.. code-block:: bash

   <path-to-venv>/bin/python -m pip install -r requirements.txt

Verify Flask-Admin:

.. code-block:: bash

   python -m pip show Flask-Admin

5. Run the Migration

```

If a previous failed SQLite batch migration left a temporary Alembic table,
remove it before retrying:

.. code-block:: bash

   sqlite3 <database-file> "DROP TABLE IF EXISTS _alembic_tmp_user;"

Run the migration:

.. code-block:: bash

   python -m flask db upgrade

Expected output includes a line similar to:

.. code-block:: text

   Running upgrade <previous_revision_id> -> <new_revision_id>, add is_admin flag to users

6. Verify the Schema
```

Check that the `is_admin` column exists:

.. code-block:: bash

   sqlite3 <database-file> "PRAGMA table_info(user);"

Expected output includes a row similar to:

.. code-block:: text

   <column_number>|is_admin|BOOLEAN|1||0

The `1` in the fourth field means that the column is `NOT NULL`.

Then verify the data:

.. code-block:: bash

   sqlite3 <database-file> "SELECT id, username, email, project_team, is_admin FROM user ORDER BY id LIMIT 30;"

Existing users should initially have:

.. code-block:: text

   is_admin = 0

7. Promote the First Administrator
```

List users:

.. code-block:: bash

   sqlite3 <database-file> "SELECT id, username, email, project_team, is_admin FROM user ORDER BY id;"

Promote the selected user:

.. code-block:: bash

   sqlite3 <database-file> "UPDATE user SET is_admin = 1 WHERE id = <admin-user-id>;"

Verify:

.. code-block:: bash

   sqlite3 <database-file> "SELECT id, username, email, project_team, is_admin FROM user WHERE id = <admin-user-id>;"

Expected result:

.. code-block:: text

   ...|1

8. Restart the Application
~~~~~~~~~~~~~~~~~~~~~~~~~~

Restart only the application process:

.. code-block:: bash

   supervisorctl restart <application-process-name>

Check that the process remains running:

.. code-block:: bash

   supervisorctl status <application-process-name>

Inspect the application logs using the normal server-specific log workflow.

Important errors to watch for:

.. code-block:: text

   ModuleNotFoundError: No module named 'flask_admin'
   sqlite3.OperationalError: no such column: user.is_admin
   BuildError

9. Test in the Browser
~~~~~~~~~~~~~~~~~~~~~~

Log out and log in again as the promoted administrator.

Then open the configured administration URL.

Expected result:

* the administration interface opens;
* the user list is available;
* the account dropdown contains the Administration link;
* the promoted user has access;
* non-admin users do not have access.

If access works in an incognito window but not in the normal browser window,
clear the site's cookies or log out and back in. The browser may still hold an
old session cookie.

Rollback
--------

If the migration or application start fails, stop the application:

.. code-block:: bash

   supervisorctl stop <application-process-name>

Restore the database backup:

.. code-block:: bash

   cp <database-backup-file> <database-file>

Roll back the code to the previous stable commit:

.. code-block:: bash

   git log --oneline -5
   git checkout <previous-good-commit>

Then restart the application:

.. code-block:: bash

   supervisorctl start <application-process-name>

Check the process status and inspect the logs using the normal server-specific
workflow.

Important Notes
---------------

Do not restart all services when only the application process needs to be
restarted. Restarting unrelated services can expose unrelated dependency or
configuration problems.

Use:

.. code-block:: bash

   supervisorctl restart <application-process-name>

or:

.. code-block:: bash

   supervisorctl stop <application-process-name>
   supervisorctl start <application-process-name>

Also avoid plain ``pip install`` unless it points to the correct virtual
environment. Prefer:

.. code-block:: bash

   python -m pip install -r requirements.txt

or:

.. code-block:: bash

   <path-to-venv>/bin/python -m pip install -r requirements.txt

This ensures that packages are installed into the environment used by the
application process.
```
