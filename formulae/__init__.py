from flask import Flask, request, session, current_app
import logging
from logging.handlers import RotatingFileHandler
import os
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from elasticsearch import Elasticsearch
from flask_bootstrap import Bootstrap
from flask_babel import Babel
from flask_babel import lazy_gettext as _l
from flask_mail import Mail
from flask_session import Session
from json import load
from redis import Redis

db = SQLAlchemy()
login = LoginManager()
login.login_view = 'auth.r_login'
login.login_message = _l("Bitte loggen Sie sich ein, um Zugang zu erhalten.")
migrate = Migrate()
bootstrap = Bootstrap()
babel = Babel()
mail = Mail()
sess = Session()


def create_app(config_class=Config):
    app = Flask("Flask Application for Nemo")
    app.config.from_object(config_class)
    if app.config['ELASTICSEARCH_URL']:
        if app.config['ES_CLIENT_CERT'] or app.config['ES_CLIENT_KEY']:
            app.elasticsearch = Elasticsearch(hosts=app.config['ELASTICSEARCH_URL'],
                                              verify_certs=True,
                                              client_cert=app.config['ES_CLIENT_CERT'],
                                              client_key=app.config['ES_CLIENT_KEY'])
        else:
            app.elasticsearch = Elasticsearch(hosts=app.config['ELASTICSEARCH_URL'])
    else:
        app.elasticsearch = None

    app.IIIFserver = app.config['IIIF_SERVER']\
        if app.config['IIIF_SERVER'] else None

    if app.config['IIIF_MAPPING']:
        app.IIIFmapping = app.config['IIIF_MAPPING']
        with open('{}/Mapping.json'.format(app.config['IIIF_MAPPING']), "r") as f:
            app.picture_file = load(f)
        for key, value in app.picture_file.items():
            if type(value) == dict:
                if 'manifest' in value.keys():
                    app.IIIFviewer = True
                    continue
                else:
                    app.IIIFviewer = False
                    app.picture_file = ""
                    break
    else:
        app.IIIFviewer = False
        app.picture_file = ""

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    bootstrap.init_app(app)
    babel.init_app(app, locale_selector=get_locale)
    sess.init_app(app)
    app.redis = Redis.from_url(app.config['REDIS_URL'])

    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/formulae-nemo.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Formulae-Nemo startup')
        app.logger.info('server type: '+Config.SERVER_TYPE+' (set in config.py)')

    from .auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    from .search import bp as search_bp
    app.register_blueprint(search_bp, url_prefix="/search")
    if app.IIIFviewer is False:
        app.logger.warning(_l('Der Viewer konnte nicht gestartet werden.'))
    else:
        from .viewer import bp as viewer_bp
        viewer_bp.static_folder = app.config['IIIF_MAPPING']
        app.register_blueprint(viewer_bp, url_prefix="/viewer")
    
    # https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-vii-error-handling
    from logging.handlers import SMTPHandler
    if app.config['MAIL_SERVER']:
            auth = None
            if app.config['MAIL_USERNAME'] or app.config['MAIL_PASSWORD']:
                auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            ### TLS handling
            secure = None
            if app.config['MAIL_USE_TLS']:
                secure = ()
            else:
                app.logger.warning("Turning of TLS is a potential risk. Please avoid it. ")
            ### setting the from email
            import re
            email_validate_pattern = r"^\S+@\S+\.\S+$"
            if re.match(email_validate_pattern, app.config['MAIL_USERNAME']):
                fromaddr = app.config['MAIL_USERNAME']
                app.logger.info("Error emails will be sent from {}. Please make sure, that all admins white listed this sender.".format(fromaddr))
            else:
                raise NotImplementedError("provided MAIL_USERNAME (see .env) is not a email address and no alternative fromaddr was given.")
            if []==app.config['ADMINS']:
                app.logger.warning("No admin addresses given -> Error Emails will go void.")
            mail_handler = SMTPHandler(
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr=fromaddr,
                toaddrs=app.config['ADMINS'], 
                subject='[werkstatt]',
                credentials=auth, secure=secure)
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)
    elif not app.config['MAIL_SERVER'] and not app.debug:
        app.logger.warning("Neither debugging nor error emails are set up. You are flying blind!")

    return app


def get_locale():
    if current_user.is_authenticated and current_user.default_locale:
        return current_user.default_locale
    if 'locale' in session:
        return session['locale']
    return request.accept_languages.best_match(current_app.config['LANGUAGES'], default='de')


from formulae import models
