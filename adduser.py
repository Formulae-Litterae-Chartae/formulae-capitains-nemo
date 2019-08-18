from formulae.app import nemo
from formulae import create_app, db
from formulae.models import User

app = create_app()
app.app_context().push()
u = User(username="Ferdinand", email="trendelenburger19.04@googlemail.com", project_team=True, default_locale="de")
u.set_password('Pa55wort')
db.session.add(u)
db.session.commit()
