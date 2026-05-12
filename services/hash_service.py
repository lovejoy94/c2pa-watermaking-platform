# ================================================================
# FICHIER  : services/hash_service.py
# ROLE     : Hash SHA-256 + Signature RSA
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
import base64
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


app = FastAPI(
    title="Hash & Signature Service",
    description="Calcule SHA-256, signe et vérifie les médias",
    version="2.0.0"
)

UPLOAD_FOLDER = "uploads"
REGISTRY = "manifests/hash_registry.json"

KEYS_FOLDER = "keys"
PRIVATE_KEY_PATH = "keys/private_key.pem"
PUBLIC_KEY_PATH = "keys/public_key.pem"


# ================================================================
# CLÉS RSA
# ================================================================

def generate_keys_if_missing():
    os.makedirs(KEYS_FOLDER, exist_ok=True)

    if os.path.exists(PRIVATE_KEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        return

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    public_key = private_key.public_key()

    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )


def load_private_key():
    generate_keys_if_missing()

    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None
        )


def load_public_key():
    generate_keys_if_missing()

    with open(PUBLIC_KEY_PATH, "rb") as f:
        return serialization.load_pem_public_key(
            f.read()
        )


# ================================================================
# OUTILS HASH
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


def save_upload(media: UploadFile) -> tuple[str, str]:
    if not media.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    unique_name = f"{uuid.uuid4()}_{media.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    return filepath, unique_name


# ================================================================
# SIGNATURE RSA
# ================================================================

def sign_hash(sha256: str) -> str:
    private_key = load_private_key()

    signature = private_key.sign(
        sha256.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )

    return base64.b64encode(signature).decode()


def verify_hash_signature(sha256: str, signature_b64: str) -> bool:
    public_key = load_public_key()

    try:
        signature = base64.b64decode(signature_b64)

        public_key.verify(
            signature,
            sha256.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

        return True

    except Exception:
        return False


# ================================================================
# ROUTE HASH
# ================================================================

@app.post("/hash")
async def compute_hash(media: UploadFile = File(...)):
    filepath, unique_name = save_upload(media)

    try:
        sha256 = compute_sha256(filepath)

        registry = load_registry()

        already_known = sha256 in registry

        filename_changed = (
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
            "filename_changed": filename_changed,
            "modified": False,
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
            "filename_changed": False,
            "modified": False,
            "status": "Erreur",
            "error": str(e)
        })

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ================================================================
# ROUTE SIGNATURE
# ================================================================

@app.post("/sign")
async def sign_media(media: UploadFile = File(...)):
    filepath, unique_name = save_upload(media)

    try:
        sha256 = compute_sha256(filepath)
        signature = sign_hash(sha256)

        return JSONResponse({
            "success": True,
            "fichier": media.filename,
            "sha256": sha256,
            "signature_algorithm": "RSA-PSS-SHA256",
            "signature": signature,
            "signed_by": "C2PA-GROUPE7",
            "signed_at": datetime.now().isoformat(),
            "error": None
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "fichier": media.filename,
            "sha256": "",
            "signature": None,
            "error": str(e)
        })

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ================================================================
# ROUTE VÉRIFICATION SIGNATURE
# ================================================================

@app.post("/verify-signature")
async def verify_signature(
    media: UploadFile = File(...),
    signature: str = ""
):
    filepath, unique_name = save_upload(media)

    try:
        if not signature:
            raise HTTPException(
                status_code=400,
                detail="Signature absente"
            )

        sha256 = compute_sha256(filepath)
        valid = verify_hash_signature(sha256, signature)

        return JSONResponse({
            "success": True,
            "fichier": media.filename,
            "sha256": sha256,
            "signature_valid": valid,
            "verified_by": "C2PA-GROUPE7",
            "error": None
        })

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


# ================================================================
# HEALTH
# ================================================================

@app.get("/health")
async def health():
    generate_keys_if_missing()

    return {
        "service": "hash_service",
        "status": "ok",
        "port": 5003,
        "features": [
            "sha256",
            "rsa_signature",
            "signature_verification"
        ],
        "public_key": PUBLIC_KEY_PATH
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