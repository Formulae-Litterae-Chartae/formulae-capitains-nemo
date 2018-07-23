from flask import Blueprint

bp = Blueprint('auth', __name__)

from formulae.auth import routes
