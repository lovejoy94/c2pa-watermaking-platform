from flask import Flask, request, jsonify
import hashlib, os, json
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
REGISTRY = 'manifests/hash_registry.json'

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def load_registry():
    if os.path.exists(REGISTRY):
        with open(REGISTRY, 'r') as f:
            return json.load(f)
    return {}

def save_registry(registry):
    os.makedirs('manifests', exist_ok=True)
    with open(REGISTRY, 'w') as f:
        json.dump(registry, f, indent=2)

@app.route('/hash', methods=['POST'])
def compute_hash():
    if 'media' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    file = request.files['media']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)

    sha256 = compute_sha256(filepath)
    registry = load_registry()
    already_known = sha256 in registry

    if not already_known:
        registry[sha256] = {
            'filename': file.filename,
            'size': os.path.getsize(filepath),
            'date': datetime.now().isoformat()
        }
        save_registry(registry)

    return jsonify({
        'sha256': sha256,
        'already_known': already_known,
        'modified': already_known and registry[sha256]['filename'] != file.filename,
        'status': 'Fichier connu' if already_known else 'Nouveau fichier'
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'service': 'hash_service', 'status': 'ok'})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(port=5003, debug=True)