from flask import Blueprint

requisiciones_bp = Blueprint('requisiciones', __name__, template_folder='templates')

from . import routes
