import os
import subprocess
from flask import Flask, request, jsonify, abort

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.post('/actualizar_prompt')
def actualizar_prompt():
    data = request.get_json(silent=True) or {}
    prompt = data.get('prompt')
    if not prompt:
        abort(400, description='Prompt requerido')

    prompt_file = os.path.join(BASE_DIR, 'prompt_actual.txt')
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    script_path = os.path.join(BASE_DIR, 'automatizador_codex.py')
    subprocess.run(['python3', script_path], check=True)

    return jsonify({'status': 'ok', 'prompt': prompt})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=False)
