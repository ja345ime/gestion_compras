from flask import Flask, request, jsonify
import os
import subprocess

app = Flask(__name__)

@app.post('/actualizar_prompt')
def actualizar_prompt():
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt') or '').strip()
    if not prompt:
        return jsonify({'error': 'El prompt está vacío'}), 400

    prompt_path = os.path.join(os.path.dirname(__file__), 'prompt_actual.txt')
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)

    subprocess.run(['python3', 'automatizador_codex.py'], cwd=os.path.dirname(__file__))

    return jsonify({'status': 'ok', 'prompt': prompt})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=False)
