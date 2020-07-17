import os
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config(object):
    SECRET_KEY = os.environ.get('NEMO_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    POSTS_PER_PAGE = 10
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL')
    ES_CLIENT_CERT = os.environ.get('ES_CLIENT_CERT', '')
    ES_CLIENT_KEY = os.environ.get('ES_CLIENT_KEY', '')
    LANGUAGES = ['en', 'de', 'fr']
    BABEL_DEFAULT_LOCALE = 'de'
    CORPUS_FOLDERS = os.environ.get('CORPUS_FOLDERS').split(';') if os.environ.get('CORPUS_FOLDERS') else ["/home/matt/results/formulae"]
    INFLECTED_LEM_JSONS = os.environ.get('INFLECTED_LEM_JSONS').split(';') if os.environ.get('INFLECTED_LEM_JSONS') else []
    LEM_TO_LEM_JSONS = os.environ.get('LEM_TO_LEM_JSONS').split(';') if os.environ.get('LEM_TO_LEM_JSONS') else []
    CACHE_DIRECTORY = os.environ.get('NEMO_CACHE_DIR') or './cache/'
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = os.environ.get('ADMINS').split(';') if os.environ.get('ADMINS') else ['no-reply@example.com']
    SESSION_TYPE = 'filesystem'
    IIIF_SERVER = os.environ.get('IIIF_SERVER')
    IIIF_MAPPING = os.environ.get('IIIF_MAPPING') or ';'.join(['{}/iiif'.format(f) for f in CORPUS_FOLDERS])
    # This should only be changed to True when collecting search queries and responses for mocking ES
    SAVE_REQUESTS = False
    CACHE_MAX_AGE = os.environ.get('VARNISH_MAX_AGE') or 0  # Only need cache on the server, where this should be set in env
    PDF_ENCRYPTION_PW = os.environ.get('PDF_ENCRYPTION_PW', 'hard_pw')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', True)
    REMEMBER_COOKIE_SECURE = os.environ.get('REMEMBER_COOKIE_SECURE', True)
