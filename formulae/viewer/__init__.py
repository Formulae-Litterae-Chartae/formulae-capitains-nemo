from flask import Blueprint, current_app
from json import load

bp = Blueprint('viewer', __name__)

from formulae.viewer import routes
