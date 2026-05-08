from flask import Flask, request, jsonify
import os, cv2, numpy as np

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'

def detect_wm_in_frame(frame):
    blue = frame[:, :, 0]
    lsb = blue & 1
    ratio = np.sum(lsb) / lsb.size
    return not (0.45 < ratio < 0.55), round(abs(ratio - 0.5) * 200)

def analyze_video(filepath):
    result = {
        'watermark_found': False,
        'confidence': 0,
        'frames_analyzed': 0,
        'frames_with_watermark': 0,
        'details': []
    }
    try:
        cap = cv2.VideoCapture(filepath)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        result['total_frames'] = total
        result['fps'] = round(fps, 2)

        step = max(1, total // 10)
        checked, wm = 0, 0
        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if not ret:
                break
            has_wm, _ = detect_wm_in_frame(frame)
            checked += 1
            if has_wm:
                wm += 1
        cap.release()

        result['frames_analyzed'] = checked
        result['frames_with_watermark'] = wm
        if checked > 0 and wm > checked * 0.5:
            result['watermark_found'] = True
            result['confidence'] = round((wm / checked) * 100)
            result['details'].append(f'WM dans {wm}/{checked} frames')
        else:
            result['details'].append('Aucun watermark detecte')
    except Exception as e:
        result['details'].append(f'Erreur: {str(e)}')
    return result

def add_watermark(filepath, message='C2PA-CERTIFIED'):
    try:
        cap = cv2.VideoCapture(filepath)
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out_path = os.path.join(OUTPUT_FOLDER, 'wm_' + os.path.basename(filepath))
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

        bits = ''.join(format(ord(c), '08b') for c in message)
        bit_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            flat = frame[:, :, 0].flatten()
            for i in range(min(len(bits), len(flat))):
                flat[i] = (flat[i] & 0xFE) | int(bits[bit_idx % len(bits)])
                bit_idx += 1
            frame[:, :, 0] = flat.reshape(frame[:, :, 0].shape)
            out.write(frame)

        cap.release()
        out.release()
        return out_path
    except Exception as e:
        return None

@app.route('/watermark-video/detect', methods=['POST'])
def detect():
    if 'media' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    file = request.files['media']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)
    return jsonify(analyze_video(filepath))

@app.route('/watermark-video/add', methods=['POST'])
def add_wm():
    if 'media' not in request.files:
        return jsonify({'error': 'Aucun fichier'}), 400
    file = request.files['media']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(filepath)

    output = add_watermark(filepath)
    if output:
        return jsonify({'success': True, 'output': output})
    return jsonify({'success': False}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'service': 'watermark_video', 'status': 'ok'})

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(port=5005, debug=True)