from flask import Flask, request, session
import logging
from logging.handlers import RotatingFileHandler
import os
from capitains_nautilus.cts.resolver import NautilusCTSResolver
from capitains_nautilus.flask_ext import FlaskNautilus
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from elasticsearch import Elasticsearch
from flask_bootstrap import Bootstrap
from flask_babel import Babel
from flask_babel import lazy_gettext as _l
from flask_mail import Mail
from werkzeug.contrib.cache import FileSystemCache
from .dispatcher_builder import organizer


flask_app = Flask("Flask Application for Nemo")
flask_app.config.from_object(Config)
db = SQLAlchemy(flask_app)
login = LoginManager(flask_app)
login.login_view = '.r_login'
login.login_message = _l("Please log in to access this page.")
migrate = Migrate(flask_app, db)
flask_app.elasticsearch = Elasticsearch(flask_app.config['ELASTICSEARCH_URL']) \
    if flask_app.config['ELASTICSEARCH_URL'] else None
bootstrap = Bootstrap(flask_app)
babel = Babel(flask_app, default_locale='de')
mail = Mail(flask_app)
resolver = NautilusCTSResolver(flask_app.config['CORPUS_FOLDERS'],
                               dispatcher=organizer,
                               cache=FileSystemCache(flask_app.config['CACHE_DIRECTORY']))

if not flask_app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/formulae-nemo.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    flask_app.logger.addHandler(file_handler)
    flask_app.logger.setLevel(logging.INFO)
    flask_app.logger.info('Formulae-Nemo startup')

@babel.localeselector
def get_locale():
    if 'locale' in session:
        return session['locale']
    if current_user.is_authenticated and current_user.default_locale:
        return current_user.default_locale
    return request.accept_languages.best_match(flask_app.config['LANGUAGES'])

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
    templates={"main": "templates/main",
               "errors": "templates/errors"},
    pdf_folder="pdf_folder/"
)


