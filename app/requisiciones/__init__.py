from flask import Blueprint

requisiciones_bp = Blueprint("requisiciones", __name__, url_prefix="/requisiciones")

from . import routes
