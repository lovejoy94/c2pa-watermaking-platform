from flask import Flask, request, jsonify
import os

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'

def analyze_c2pa(filepath):
    result = {
        'has_manifest': False,
        'certified': False,
        'tool_used': None,
        'ai_generated': False,
        'modifications': [],
        'details': 'Aucun manifeste C2PA detecte'
    }
    try:
        with open(filepath, 'rb') as f:
            data = f.read()

        markers = [b'c2pa', b'C2PA', b'contentCredentials', b'c2pa.assertions', b'c2pa.claim']
        for marker in markers:
            if marker in data:
                result['has_manifest'] = True
                result['certified'] = True
                result['details'] = f'Manifeste C2PA detecte ({marker.decode()})'
                break

        if b'Adobe' in data or b'Photoshop' in data:
            result['tool_used'] = 'Adobe Photoshop / Firefly'
            result['modifications'].append('Edite avec Adobe')
        elif b'DALL-E' in data or b'OpenAI' in data:
            result['tool_used'] = 'OpenAI DALL-E'
            result['ai_generated'] = True
        elif b'Midjourney' in data:
            result['tool_used'] = 'Midjourney'
            result['ai_generated'] = True

        if b'GIMP' in data:
            result['modifications'].append('Retouche avec GIMP')
        if b'generatedBy' in data:
            result['ai_generated'] = True
            result['modifications'].append('Contenu IA detecte')

    except Exception as e:
        result['details'] = f'Erreur: {str(e)}'
    return result

@app.route('/c2pa', methods=['POST'])
def verify_c2pa():
    if 'media' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    file = request.files['media']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)

    result = analyze_c2pa(filepath)
    return jsonify(result)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'service': 'c2pa_service', 'status': 'ok'})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(port=5004, debug=True)