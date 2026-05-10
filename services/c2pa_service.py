#voila c2pa_service.py
# ================================================================
# FICHIER  : services/c2pa_service.py cherche la preuve d'authenticite
# ROLE     : Microservice analyse C2PA et preuve
# PORT     : 5004
# LANCER   : python -m uvicorn services.c2pa_service:app --port 5004 --reload
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
import uuid

app = FastAPI(
    title="C2PA Service",
    description="Analyse le manifeste C2PA d'un média",
    version="1.0.0"
)

UPLOAD_FOLDER = "uploads"

# ================================================================
# LOGIQUE C2PA
# ================================================================

def analyze_c2pa(filepath: str, filename: str) -> dict:
    """
    Analyse un média afin de détecter :
    - un manifeste C2PA
    - un outil IA connu
    - des traces de modification
    """

    result = {
        "success": True,

        # Convention projet
        "fichier": filename,
        "type_media": "unknown",

        # C2PA
        "has_manifest": False,
        "c2pa_certified": False,

        # IA
        "ai_generated": False,

        # Infos complémentaires
        "tool_used": None,
        "modifications": [],

        # Messages
        "details": "Aucun manifeste C2PA détecté",
        "error": None
    }

    try:

        with open(filepath, "rb") as file:
            data = file.read()

        # ========================================================
        # DETECTION C2PA
        # ========================================================

        markers = [
            b"c2pa",
            b"C2PA",
            b"contentCredentials",
            b"c2pa.assertions",
            b"c2pa.claim"
        ]

        for marker in markers:

            if marker in data:

                result["has_manifest"] = True
                result["c2pa_certified"] = True

                result["details"] = (
                    f"Manifeste C2PA détecté ({marker.decode(errors='ignore')})"
                )

                break

        # ========================================================
        # DETECTION OUTIL IA / RETOUCHE
        # ========================================================

        if b"Adobe" in data or b"Photoshop" in data:

            result["tool_used"] = "Adobe Photoshop / Firefly"

            result["modifications"].append(
                "Édité avec Adobe"
            )

        elif b"DALL-E" in data or b"OpenAI" in data:

            result["tool_used"] = "OpenAI DALL-E"

            result["ai_generated"] = True

            result["modifications"].append(
                "Contenu généré avec DALL-E"
            )

        elif b"Midjourney" in data:

            result["tool_used"] = "Midjourney"

            result["ai_generated"] = True

            result["modifications"].append(
                "Contenu généré avec Midjourney"
            )

        elif b"StableDiffusion" in data:

            result["tool_used"] = "Stable Diffusion"

            result["ai_generated"] = True

            result["modifications"].append(
                "Contenu généré avec Stable Diffusion"
            )

        # ========================================================
        # DETECTION MODIFICATIONS
        # ========================================================

        if b"GIMP" in data:

            result["modifications"].append(
                "Retouche avec GIMP"
            )

        if b"generatedBy" in data:

            result["ai_generated"] = True

            result["modifications"].append(
                "Métadonnée IA détectée"
            )

    except Exception as e:

        result["success"] = False

        result["error"] = str(e)

        result["details"] = f"Erreur analyse : {str(e)}"

    return result

# ================================================================
# ROUTES
# ================================================================

@app.post("/c2pa")
async def verify_c2pa(media: UploadFile = File(...)):
    """
    Reçoit un média et analyse son manifeste C2PA.
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

    # Sauvegarde temporaire
    with open(filepath, "wb") as file:

        shutil.copyfileobj(
            media.file,
            file
        )

    try:

        result = analyze_c2pa(
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

# ================================================================
# HEALTH
# ================================================================

@app.get("/health")
async def health():

    return {
        "service": "c2pa_service",
        "status": "ok",
        "port": 5004
    }

# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        
        "services.c2pa_service:app",
        host="0.0.0.0",
        port=5004,
        reload=True
    )