from flask import Blueprint, request, jsonify
import subprocess

telegram_bp = Blueprint('telegram_bp', __name__)

@telegram_bp.route('/telegram/<token>', methods=['POST'])
def recibir_mensaje(token):
    if token != '8118390517:AAExNtzT1v_RGt-F_18dizJvTV97U-0MA-o':
        return jsonify({"error": "Token inválido"}), 403

    data = request.json
    mensaje = data.get('message', {}).get('text', '')

    if mensaje.startswith("prompt:"):
        # Enviar directamente a Codex
        with open("prompt_actual.txt", "w") as f:
            f.write(mensaje.replace("prompt:", "").strip())
        subprocess.Popen(["python3", "automatizador_codex.py"])
        return jsonify({"ok": True, "msg": "Prompt enviado a Codex directamente"}), 200
    else:
        # Guardar como sugerencia para mejorar con GPT
        with open("entrada_usuario.txt", "w") as f:
            f.write(mensaje.strip())
        subprocess.Popen(["python3", "estructurador_gpt.py"])
        return jsonify({"ok": True, "msg": "Mensaje enviado para estructuración GPT"}), 200

