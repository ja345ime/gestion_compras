from flask import Blueprint

telegram_bp = Blueprint('telegram', __name__)

@telegram_bp.route('/telegram/<token>', methods=['POST'])
def handle_webhook(token):
    return 'Webhook recibido correctamente', 200
