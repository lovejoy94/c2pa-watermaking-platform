# ================================================================
# FICHIER  : services/watermark_video.py
# ROLE     : Microservice watermark vidéo robuste
# PORT     : 5005
# LANCER   : python -m uvicorn services.watermark_video:app --port 5005 --reload
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
import uuid
import cv2
import hashlib
import json
from datetime import datetime

app = FastAPI(
    title="Watermark Video Service",
    description="Ajoute et détecte une signature invisible dans une vidéo",
    version="2.2.0"
)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

SECRET_KEY = os.getenv("WATERMARK_SECRET_KEY", "C2PA-GROUPE7-SECRET-KEY")

MAX_UPLOAD_SIZE_BYTES = 700 * 1024 * 1024

SIGNATURE_PREFIX = "C2PAWM"
START_MARKER = "START_C2PAWM::"
END_MARKER = "::END_C2PAWM"


# ================================================================
# OUTILS SIGNATURE
# ================================================================

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()

    with open(filepath, "rb") as file:
        while True:
            chunk = file.read(8192)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def sign_payload(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()


def text_to_bits(text: str) -> str:
    return "".join(format(ord(c), "08b") for c in text)


def bits_to_text(bits: str) -> str:
    chars = []

    for i in range(0, len(bits), 8):
        byte = bits[i:i + 8]

        if len(byte) == 8:
            chars.append(chr(int(byte, 2)))

    return "".join(chars)


def build_watermark_payload(sha256_before: str) -> str:
    """
    Crée un watermark signé contenant :
    - identifiant projet
    - identifiant média
    - hash original
    - date
    - émetteur
    - signature cryptographique
    """

    payload = {
        "project": "C2PA-GROUPE7",
        "media_id": str(uuid.uuid4()),
        "sha256_original": sha256_before,
        "created_at": datetime.now().isoformat(),
        "issuer": "C2PA-Service-Groupe7"
    }

    signature = sign_payload(payload)

    package = {
        "prefix": SIGNATURE_PREFIX,
        "payload": payload,
        "signature": signature
    }

    json_data = json.dumps(
        package,
        separators=(",", ":"),
        ensure_ascii=False
    )

    return f"{START_MARKER}{json_data}{END_MARKER}"


def verify_watermark_package(text: str) -> dict | None:
    """
    Extrait et vérifie le watermark signé.
    Retourne le package si valide.
    """

    try:
        start = text.find(START_MARKER)
        end = text.find(END_MARKER)

        if start == -1 or end == -1:
            return None

        json_text = text[start + len(START_MARKER):end]

        package = json.loads(json_text)

        if package.get("prefix") != SIGNATURE_PREFIX:
            return None

        payload = package.get("payload", {})
        signature = package.get("signature", "")

        expected_signature = sign_payload(payload)

        if signature != expected_signature:
            return None

        return package

    except Exception:
        return None


# ================================================================
# WATERMARK AJOUT
# ================================================================

def add_watermark(filepath: str) -> str | None:
    """
    Ajoute un watermark invisible signé dans toutes les frames.

    Version robuste :
    - watermark signé
    - insertion dans toutes les frames
    - sortie AVI
    - codec FFV1 lossless si disponible
    - fallback MJPG
    """

    try:
        sha256_original = compute_sha256(filepath)

        cap = cv2.VideoCapture(filepath)

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if width == 0 or height == 0:
            cap.release()
            return None

        if fps <= 0:
            fps = 25

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(filepath))[0]

        out_path = os.path.join(
            OUTPUT_FOLDER,
            "wm_" + base_name + ".avi"
        )

        fourcc = cv2.VideoWriter_fourcc(*"FFV1")

        out = cv2.VideoWriter(
            out_path,
            fourcc,
            fps,
            (width, height)
        )

        if not out.isOpened():
            fourcc = cv2.VideoWriter_fourcc(*"MJPG")

            out = cv2.VideoWriter(
                out_path,
                fourcc,
                fps,
                (width, height)
            )

        if not out.isOpened():
            cap.release()
            return None

        watermark_text = build_watermark_payload(sha256_original)
        bits = text_to_bits(watermark_text)

        frame_index = 0
        frames_watermarked = 0

        while cap.isOpened():
            ret, frame = cap.read()

            if not ret:
                break

            blue = frame[:, :, 0].flatten()

            max_bits = min(len(bits), len(blue))

            for i in range(max_bits):
                blue[i] = (blue[i] & 0xFE) | int(bits[i])

            frame[:, :, 0] = blue.reshape(frame[:, :, 0].shape)

            out.write(frame)

            frame_index += 1
            frames_watermarked += 1

        cap.release()
        out.release()

        if frames_watermarked == 0:
            return None

        return out_path

    except Exception as e:
        print(f"Erreur ajout watermark : {e}")
        return None


# ================================================================
# WATERMARK DETECTION
# ================================================================

def extract_watermark_from_frame(frame, max_chars: int = 2000) -> str:
    """
    Relit les bits cachés dans le canal bleu d'une frame.
    """

    blue = frame[:, :, 0].flatten()

    bits_needed = min(max_chars * 8, len(blue))

    bits = "".join(
        str(blue[i] & 1)
        for i in range(bits_needed)
    )

    return bits_to_text(bits)


def analyze_video(filepath: str, filename: str) -> dict:
    """
    Analyse une vidéo et vérifie une signature watermark signée.
    """

    result = {
        "success": True,
        "fichier": filename,
        "type_media": "video",
        "watermark_found": False,
        "confidence": 0,
        "frames_analyzed": 0,
        "frames_with_watermark": 0,
        "watermark_metadata": None,
        "details": [],
        "error": None
    }

    try:
        cap = cv2.VideoCapture(filepath)

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        result["total_frames"] = total
        result["fps"] = round(fps, 2)

        if total <= 0:
            result["details"].append("Vidéo illisible ou sans frame")
            cap.release()
            return result

        step = 1

        checked = 0
        detected = 0
        extracted_package = None

        for i in range(0, total, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)

            ret, frame = cap.read()

            if not ret:
                break

            extracted_text = extract_watermark_from_frame(frame)

            checked += 1

            package = verify_watermark_package(extracted_text)

            if package is not None:
                detected += 1

                if extracted_package is None:
                    extracted_package = package

        cap.release()

        result["frames_analyzed"] = checked
        result["frames_with_watermark"] = detected

        if detected > 0:
            result["watermark_found"] = True
            result["confidence"] = round((detected / checked) * 100)

            if extracted_package:
                result["watermark_metadata"] = extracted_package.get("payload", {})

            result["details"].append(
                f"Watermark signé valide détecté dans {detected}/{checked} frames"
            )

            result["details"].append(
                "Signature cryptographique vérifiée avec succès"
            )

        else:
            result["details"].append(
                "Aucun watermark signé valide détecté"
            )

    except Exception as e:
        result["success"] = False
        result["error"] = str(e)
        result["details"].append(
            f"Erreur analyse : {str(e)}"
        )

    return result


# ================================================================
# ROUTES
# ================================================================

@app.post("/watermark-video/detect")
async def detect(media: UploadFile = File(...)):

    if not media.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    media.file.seek(0, 2)
    file_size = media.file.tell()
    media.file.seek(0)

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux. Maximum autorisé : {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} Mo"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{media.filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    with open(filepath, "wb") as file:
        shutil.copyfileobj(media.file, file)

    try:
        result = analyze_video(filepath, media.filename)
        return JSONResponse(result)

    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:
            print(f"Erreur suppression fichier : {e}")


@app.post("/watermark-video/add")
async def add_wm(media: UploadFile = File(...)):

    if not media.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    media.file.seek(0, 2)
    file_size = media.file.tell()
    media.file.seek(0)

    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux. Maximum autorisé : {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} Mo"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{media.filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    with open(filepath, "wb") as file:
        shutil.copyfileobj(media.file, file)

    try:
        output = add_watermark(filepath)

        if output:
            return JSONResponse({
                "success": True,
                "fichier": media.filename,
                "type_media": "video",
                "output": output,
                "details": [
                    "Watermark signé ajouté avec succès",
                    "Signature invisible intégrée dans toutes les frames",
                    "Sortie générée en AVI pour meilleure stabilité"
                ],
                "error": None
            })

        return JSONResponse({
            "success": False,
            "fichier": media.filename,
            "type_media": "video",
            "output": None,
            "error": "Échec ajout watermark"
        }, status_code=500)

    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)

        except Exception as e:
            print(f"Erreur suppression fichier : {e}")


@app.get("/")
async def home():
    return {
        "service": "watermark_video",
        "message": "Watermark Video Service actif",
        "version": "2.2.0",
        "routes": {
            "health": "/health",
            "detect": "/watermark-video/detect",
            "add": "/watermark-video/add",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    return {
        "service": "watermark_video",
        "status": "ok",
        "port": 5005
    }


# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.watermark_video:app",
        host="0.0.0.0",
        port=5005,
        reload=True
    )