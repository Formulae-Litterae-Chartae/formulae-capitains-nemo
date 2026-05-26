from flask import Flask, request, session, current_app
import logging
from logging.handlers import RotatingFileHandler
import os
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from elasticsearch import Elasticsearch
from elasticsearch import AuthenticationException
from flask_bootstrap import Bootstrap
from flask_babel import Babel
from flask_babel import lazy_gettext as _l
from flask_mail import Mail
from flask_session import Session
from json import load
from redis import Redis

from formulae.logging_handlers import ErrorSMTPHandler

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
    #########################################
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler(
            'logs/formulae-nemo.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Formulae-Nemo is starting...')
        app.logger.info('server type: %s (set in config.py)', Config.SERVER_TYPE)
    ###################################


    if app.config['ELASTICSEARCH_URL']:
        if app.config['ES_API_KEY']:
            es_api_key = app.config["ES_API_KEY"].strip()
            
            if len(es_api_key) % 4 >0:
                app.logger.warning('ES_API_KEY looks wrong: Standard Base64 strings usually have a length divisible by 4.' \
                'The provided key is l={}'.format(len(es_api_key)))
            if es_api_key.startswith(("'", '"')) and es_api_key.endswith(("'", '"')):
                app.logger.warning("ES_API_KEY looks wrong: it contains \" and/or '")
            app.logger.info("Try connect to Elastic Search via API key (l={})".format(len(es_api_key)))
            app.elasticsearch = Elasticsearch(
                hosts=app.config['ELASTICSEARCH_URL'],
                verify_certs=False,
                api_key=es_api_key,
                request_timeout=60,
                max_retries=2,
                retry_on_timeout=True,
            )
            try:
                info = app.elasticsearch.info()
                app.logger.info(
                    "Connected to Elasticsearch via API key: %s",
                    info.get("cluster_name", "unknown cluster"),
                )
            except AuthenticationException as exc:
                app.logger.error(
                    "Elasticsearch authentication failed with 401. "
                    "This usually means the API key is missing, malformed, quoted, "
                    "truncated, invalidated, or belongs to another Elasticsearch cluster."
                )
                app.logger.debug("AuthenticationException details: %r", exc)

            except Exception:
                app.logger.exception("Elasticsearch connection failed.")
        else:
            app.elasticsearch = Elasticsearch(hosts=app.config['ELASTICSEARCH_URL'])

            try:
                info = app.elasticsearch.info()
                app.logger.warning(
                    "Connected to Elasticsearch via username and password in the URL: %s. This is a security RISK!",
                    info.get("cluster_name", "unknown cluster"),
                )
            except Exception:
                app.logger.exception("Elasticsearch via username and password in the URL failed.")
        
    else:
        app.elasticsearch = None

    app.IIIFserver = app.config['IIIF_SERVER'] if app.config['IIIF_SERVER'] else None

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

    if app.config['MAIL_SERVER']:
        import re
        import socket
        import subprocess
        import traceback

        auth = None
        if app.config['MAIL_USERNAME'] and app.config['MAIL_PASSWORD']:
            auth = (app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])

        secure = None
        if app.config['MAIL_USE_TLS']:
            secure = ()
        else:
            app.logger.warning("Turning off TLS is a potential risk. Please avoid it.")

        email_validate_pattern = r"^\S+@\S+\.\S+$"
        if re.match(email_validate_pattern, app.config['MAIL_DEFAULT_SENDER']):
            fromaddr = app.config['MAIL_DEFAULT_SENDER']
        elif re.match(email_validate_pattern, app.config['MAIL_USERNAME']):
            fromaddr = app.config['MAIL_USERNAME']
        else:
            raise NotImplementedError(
                "Provided MAIL_USERNAME (see .env) is not an email address and no alternative fromaddr was given."
            )

        app.logger.info(
            "Error emails will be sent from %s. Please make sure that all admins whitelisted this sender.",
            fromaddr
        )

        if [] == app.config['ADMINS']:
            app.logger.warning("No admin addresses given -> error emails will go void.")
        else:
            from formulae.logging_handlers import ErrorSMTPHandler

            hostname = socket.gethostname()

            def _safe_git(cmd):
                try:
                    return subprocess.check_output(
                        cmd,
                        stderr=subprocess.DEVNULL,
                        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    ).decode("utf-8").strip()
                except Exception:
                    return "unknown"

            def _normalize_remote(url):
                if not url or url == "unknown":
                    return None

                url = url.strip()

                # git@github.com:org/repo.git
                if url.startswith("git@"):
                    host_and_path = url[4:]
                    if ":" not in host_and_path:
                        return None
                    host, path = host_and_path.split(":", 1)
                    url = f"https://{host}/{path}"

                # ssh://git@github.com/org/repo.git
                elif url.startswith("ssh://git@"):
                    url = url.replace("ssh://git@", "https://", 1)

                # https://github.com/org/repo.git
                elif url.startswith("http://") or url.startswith("https://"):
                    pass

                else:
                    return None

                if url.endswith(".git"):
                    url = url[:-4]

                return url

            git_branch = _safe_git(["git", "rev-parse", "--abbrev-ref", "HEAD"])
            git_commit = _safe_git(["git", "rev-parse", "HEAD"])
            # https://stackoverflow.com/a/16880000/7924573
            git_remote = _safe_git(["git", "ls-remote", "--get-url"])

            remote_url = _normalize_remote(git_remote)

            if remote_url and git_branch != "unknown":
                branch_text = f"{git_branch} ({remote_url}/tree/{git_branch})"
            else:
                branch_text = git_branch

            if remote_url and git_commit != "unknown":
                commit_text = f"{git_commit} ({remote_url}/commit/{git_commit})"
            else:
                commit_text = git_commit

            class ErrorMailFormatter(logging.Formatter):
                def format(self, record):
                    message = record.getMessage()

                    traceback_text = ""
                    if record.exc_info:
                        traceback_text = "".join(traceback.format_exception(*record.exc_info))
                    elif record.stack_info:
                        traceback_text = record.stack_info

                    return (
                        f"{message}\n\n"
                        f"Host: {hostname}\n"
                        f"Current branch: {branch_text}\n"
                        f"Last commit id: {commit_text}\n\n"
                        f"{traceback_text}"
                    )

            error_mail_handler = ErrorSMTPHandler(
                hostname=hostname,
                mailhost=(app.config['MAIL_SERVER'], app.config['MAIL_PORT']),
                fromaddr=fromaddr,
                toaddrs=app.config['ADMINS'],
                subject='[werkstatt] Error',  # ignored by handler; only fallback
                credentials=auth,
                secure=secure
            )
            error_mail_handler.setLevel(logging.ERROR)
            error_mail_handler.setFormatter(ErrorMailFormatter())
            app.logger.addHandler(error_mail_handler)

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