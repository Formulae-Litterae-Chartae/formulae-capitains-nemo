import os
from dotenv import load_dotenv
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config(object):
    SECRET_KEY = os.environ.get('NEMO_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    POSTS_PER_PAGE = 10
    # if the environment variables ELASTICSEARCH_URL is not set; the application is starting without it
    ELASTICSEARCH_URL = os.environ.get('ELASTICSEARCH_URL').split(';') if os.environ.get('ELASTICSEARCH_URL') else False
    ES_CLIENT_CERT = os.environ.get('ES_CLIENT_CERT', '')
    ES_CLIENT_KEY = os.environ.get('ES_CLIENT_KEY', '')
    LANGUAGES = ['en', 'de', 'fr']
    BABEL_DEFAULT_LOCALE = 'de'
    CORPUS_FOLDERS = os.environ.get('CORPUS_FOLDERS').split(';') if os.environ.get('CORPUS_FOLDERS') else ["../formulae-corpora/"]
    INFLECTED_LEM_JSONS = os.environ.get('INFLECTED_LEM_JSONS').split(';') if os.environ.get('INFLECTED_LEM_JSONS') else []
    LEM_TO_LEM_JSONS = os.environ.get('LEM_TO_LEM_JSONS').split(';') if os.environ.get('LEM_TO_LEM_JSONS') else []
    DEAD_URLS = os.environ.get('DEAD_URLS').split(';') if os.environ.get('DEAD_URLS') else []
    COMP_PLACES = os.environ.get('COMP_PLACES').split(';') if os.environ.get('COMP_PLACES') else []
    LEMMA_LISTS = os.environ.get('LEMMA_LISTS').split(';') if os.environ.get('LEMMA_LISTS') else []
    COLLECTED_COLLS = os.environ.get('COLLECTED_COLLS').split(';') if os.environ.get('COLLECTED_COLLS') else []
    # TERM_VECTORS = os.environ.get('TERM_VECTORS')
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
    REDIS_URL = os.environ.get('REDIS_URL') or 'redis://'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'http')
    VIDEO_FOLDER = os.environ.get('VIDEO_FOLDER') or ''
    COLLATE_API_URL = os.environ.get('COLLATE_API_URL', 'http://localhost:7300')
    WORD_GRAPH_API_URL = os.environ.get('WORD_GRAPH_API_URL', '')
    # Used to decide whether authentication is needed for certain resources (dev -> access to all without restriction; production -> restricted access for non-authenticated users)
    SERVER_TYPE = os.environ.get('SERVER_TYPE', 'dev')
    # Number of texts a not-authenticated user should be able to see. int > 0
    try:
        MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER = int(os.environ.get('MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER'))
        if not MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER > 0:
            MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER = 1
    except TypeError:
        MAX_NUMBER_OF_TEXTS_FOR_NOT_AUTHENTICATED_USER = 1

