from flask import Flask
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from capitains_nautilus.flask_ext import FlaskNautilus
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate


flask_app = Flask("Flask Application for Nemo")
flask_app.config.from_object(Config)
db = SQLAlchemy(flask_app)
login = LoginManager(flask_app)
login.login_view = '.r_login'
migrate = Migrate(flask_app, db)
resolver = NautilusCTSResolver(["/home/matt/results/formulae"])
resolver.parse()

from formulae import models

nautilus_api = FlaskNautilus(prefix="/api", resolver=resolver, app=flask_app)

from .nemo import NemoFormulae

nemo = NemoFormulae(
    name="InstanceNemo",
    app=flask_app,
    resolver=resolver,
    base_url="",
    css=["assets/css/theme.css"],
    js=["assets/js/empty.js"],
    static_folder="./assets/",
    transform={"default": "components/epidoc.xsl",
               "notes": "components/extract_notes.xsl"},
    templates={"main": "templates/main"},
    pdf_folder="pdf_folder/"
)



