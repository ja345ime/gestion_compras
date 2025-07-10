from flask import Blueprint, request, jsonify
import os
from pathlib import Path

telegram_bp = Blueprint('telegram', __name__)

# SECURITY: Define a safe directory for file operations
SAFE_DIR = Path(__file__).parent / "telegram_files"
SAFE_DIR.mkdir(exist_ok=True)

def validate_filename(filename):
    """
    Validates filename to prevent directory traversal attacks.
    """
    # Remove any path separators and relative path components
    safe_filename = os.path.basename(filename)
    # Additional validation - only allow alphanumeric, underscore, dot, hyphen
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    if not all(c in allowed_chars for c in safe_filename):
        return None
    # Prevent hidden files and files with multiple extensions
    if safe_filename.startswith('.') or safe_filename.count('.') > 1:
        return None
    return safe_filename

@telegram_bp.route('/telegram/webhook', methods=['POST'])
def telegram_webhook():
    data = request.get_json()
    
    if data and 'message' in data:
        message_text = data['message'].get('text', '')
        
        # FIXED: Use safe file paths to prevent directory traversal
        safe_prompt_filename = validate_filename("prompt_actual.txt")
        safe_input_filename = validate_filename("entrada_usuario.txt")
        
        if safe_prompt_filename and safe_input_filename:
            prompt_file = SAFE_DIR / safe_prompt_filename
            input_file = SAFE_DIR / safe_input_filename
            
            try:
                with open(prompt_file, "w") as f:
                    f.write(message_text)
                
                with open(input_file, "w") as f:
                    f.write(message_text)
                    
                return jsonify({"status": "success"})
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            return jsonify({"status": "error", "message": "Invalid filename"}), 400
    
    return jsonify({"status": "ok"})

