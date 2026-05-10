# ================================================================
# FICHIER  : services/watermark_video.py
# ROLE     : Microservice détection watermark vidéo  ajout ou detecte une signature invisible dans une video
# PORT     : 5005
# LANCER   : python -m uvicorn services.watermark_video:app --port 5005 --reload
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
import uuid
import cv2
import numpy as np

app = FastAPI(
    title="Watermark Video Service",
    description="Détecte le watermark dans une vidéo",
    version="1.0.0"
)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"

# ================================================================
# UTILITAIRES
# ================================================================

def detect_wm_in_frame(frame) -> tuple:
    """
    Détecte un watermark LSB dans une frame vidéo.
    """

    blue = frame[:, :, 0]

    lsb = blue & 1

    ratio = np.sum(lsb) / lsb.size

    confidence = round(abs(ratio - 0.5) * 200)

    return not (0.45 < ratio < 0.55), confidence


def analyze_video(filepath: str, filename: str) -> dict:
    """
    Analyse une vidéo afin de détecter un watermark.
    """

    result = {

        "success": True,

        # Convention projet
        "fichier": filename,
        "type_media": "video",

        # Watermark
        "watermark_found": False,
        "confidence": 0,

        # Analyse vidéo
        "frames_analyzed": 0,
        "frames_with_watermark": 0,

        # Informations complémentaires
        "details": [],

        # Erreur éventuelle
        "error": None
    }

    try:

        cap = cv2.VideoCapture(filepath)

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        fps = cap.get(cv2.CAP_PROP_FPS)

        result["total_frames"] = total

        result["fps"] = round(fps, 2)

        # Analyse seulement une partie des frames
        step = max(1, total // 10)

        checked = 0

        wm = 0

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

        result["frames_analyzed"] = checked

        result["frames_with_watermark"] = wm

        # ========================================================
        # RESULTAT FINAL
        # ========================================================

        if checked > 0 and wm > checked * 0.5:

            result["watermark_found"] = True

            result["confidence"] = round((wm / checked) * 100)

            result["details"].append(
                f"Watermark détecté dans {wm}/{checked} frames"
            )

        else:

            result["details"].append(
                "Aucun watermark détecté"
            )

    except Exception as e:

        result["success"] = False

        result["error"] = str(e)

        result["details"].append(
            f"Erreur analyse : {str(e)}"
        )

    return result


def add_watermark(filepath: str,
                  message: str = "C2PA-CERTIFIED") -> str | None:
    """
    Ajoute un watermark LSB dans une vidéo.
    """

    try:

        cap = cv2.VideoCapture(filepath)

        fps = cap.get(cv2.CAP_PROP_FPS)

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))

        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        out_path = os.path.join(
            OUTPUT_FOLDER,
            "wm_" + os.path.basename(filepath)
        )

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        out = cv2.VideoWriter(
            out_path,
            fourcc,
            fps,
            (width, height)
        )

        bits = "".join(
            format(ord(c), "08b")
            for c in message
        )

        bit_idx = 0

        while cap.isOpened():

            ret, frame = cap.read()

            if not ret:
                break

            flat = frame[:, :, 0].flatten()

            for i in range(min(len(bits), len(flat))):

                flat[i] = (
                    (flat[i] & 0xFE)
                    | int(bits[bit_idx % len(bits)])
                )

                bit_idx += 1

            frame[:, :, 0] = flat.reshape(
                frame[:, :, 0].shape
            )

            out.write(frame)

        cap.release()

        out.release()

        return out_path

    except Exception as e:

        print(f"Erreur ajout watermark : {e}")

        return None

# ================================================================
# ROUTES
# ================================================================

@app.post("/watermark-video/detect")
async def detect(media: UploadFile = File(...)):
    """
    Détecte un watermark dans une vidéo.
    """

    if not media.filename:

        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{media.filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    with open(filepath, "wb") as file:

        shutil.copyfileobj(
            media.file,
            file
        )

    try:

        result = analyze_video(
            filepath,
            media.filename
        )

        return JSONResponse(result)

    finally:

        try:

            if os.path.exists(filepath):

                os.remove(filepath)

        except Exception as e:

            print(
                f"Erreur suppression fichier : {e}"
            )


@app.post("/watermark-video/add")
async def add_wm(media: UploadFile = File(...)):
    """
    Ajoute un watermark dans une vidéo.
    """

    if not media.filename:

        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{media.filename}"

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    with open(filepath, "wb") as file:

        shutil.copyfileobj(
            media.file,
            file
        )

    try:

        output = add_watermark(filepath)

        if output:

            return JSONResponse({

                "success": True,

                "fichier": media.filename,

                "output": output,

                "error": None
            })

        return JSONResponse({

            "success": False,

            "fichier": media.filename,

            "output": None,

            "error": "Échec ajout watermark"

        }, status_code=500)

    finally:

        try:

            if os.path.exists(filepath):

                os.remove(filepath)

        except Exception as e:

            print(
                f"Erreur suppression fichier : {e}"
            )

# ================================================================
# HEALTH
# ================================================================

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