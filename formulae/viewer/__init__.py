from flask import Blueprint
from MyCapytain.errors import UnknownCollection
from ..errors.handlers import e_unknown_collection_error

bp = Blueprint('viewer', __name__)
bp.register_error_handler(UnknownCollection, e_unknown_collection_error)

from formulae.viewer import routes
