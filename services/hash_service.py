# ================================================================
# FICHIER  : services/hash_service.py
# ROLE     : Microservice calcul hash SHA-256
# PORT     : 5003
# LANCER   : python -m uvicorn services.hash_service:app --port 5003 --reload
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import hashlib
import shutil
import json
import os
import uuid
from datetime import datetime

app = FastAPI(
    title="Hash Service",
    description="Calcule et vérifie le hash SHA-256 d'un média",
    version="1.0.0"
)

UPLOAD_FOLDER = "uploads"
REGISTRY      = "manifests/hash_registry.json"

# ================================================================
# UTILITAIRES
# ================================================================

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()

    with open(filepath, "rb") as f:

        while chunk := f.read(8192):
            h.update(chunk)

    return h.hexdigest()


def load_registry() -> dict:

    if os.path.exists(REGISTRY):

        with open(REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def save_registry(registry: dict):

    os.makedirs("manifests", exist_ok=True)

    with open(REGISTRY, "w", encoding="utf-8") as f:

        json.dump(
            registry,
            f,
            indent=2,
            ensure_ascii=False
        )

# ================================================================
# ROUTES
# ================================================================

@app.post("/hash")
async def compute_hash(media: UploadFile = File(...)):

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

    with open(filepath, "wb") as f:

        shutil.copyfileobj(
            media.file,
            f
        )

    try:

        sha256 = compute_sha256(filepath)

        registry = load_registry()

        already_known = sha256 in registry

        modified = (
            already_known and
            registry[sha256]["filename"] != media.filename
        )

        if not already_known:

            registry[sha256] = {
                "filename": media.filename,
                "size": os.path.getsize(filepath),
                "date": datetime.now().isoformat()
            }

            save_registry(registry)

        return JSONResponse({

            "success": True,

            "fichier": media.filename,

            "sha256": sha256,

            "already_known": already_known,

            "modified": modified,

            "status": (
                "Fichier connu"
                if already_known
                else "Nouveau fichier enregistré"
            ),

            "error": None
        })

    except Exception as e:

        return JSONResponse({

            "success": False,

            "fichier": media.filename,

            "sha256": "",

            "already_known": False,

            "modified": False,

            "status": "Erreur",

            "error": str(e)
        })

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
        "service": "hash_service",
        "status": "ok",
        "port": 5003
    }

# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "services.hash_service:app",
        host="0.0.0.0",
        port=5003,
        reload=True
    )