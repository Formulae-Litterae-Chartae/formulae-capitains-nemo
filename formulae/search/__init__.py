from flask import Blueprint

bp = Blueprint('search', __name__)

from formulae.search import routes
