#voila c2pa_service.py
# ================================================================
# FICHIER  : services/c2pa_service.py cherche la preuve d'authenticite
# ROLE     : Microservice analyse C2PA et preuve
# PORT     : 5004
# LANCER   : python -m uvicorn services.c2pa_service:app --port 5004 --reload
# ================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
import shutil
import os
import uuid
import hashlib
import subprocess
import asyncio
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("c2pa_service")

UPLOAD_FOLDER = "uploads"

MAX_UPLOAD_SIZE_BYTES = 700 * 1024 * 1024
FALLBACK_CHUNK_SIZE = 65_536
FALLBACK_MAX_READ = 20 * 1024 * 1024
UPLOAD_TTL_SECONDS = 3600

C2PATOOL_PATH = os.getenv("C2PATOOL_PATH", "c2patool")

ALLOWED_EXTENSIONS: dict[str, str] = {
    "jpg": "image",
    "jpeg": "image",
    "png": "image",
    "webp": "image",
    "heic": "image",
    "heif": "image",
    "mp3": "audio",
    "wav": "audio",
    "flac": "audio",
    "ogg": "audio",
    "aac": "audio",
    "m4a": "audio",
    "mp4": "video",
    "avi": "video",
    "mov": "video",
    "mkv": "video",
    "webm": "video",
    "pdf": "document",
    "docx": "document",
    "xlsx": "document",
    "pptx": "document",
    "txt": "document",
}


def get_safe_extension(filename: str) -> str | None:
    parts = filename.rsplit(".", 1)

    if len(parts) != 2:
        return None

    ext = parts[1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


def check_magic_bytes(filepath: str, ext: str) -> bool:
    try:
        with open(filepath, "rb") as f:
            header = f.read(64)

        if ext in ["jpg", "jpeg"]:
            return header.startswith(b"\xff\xd8\xff")

        if ext == "png":
            return header.startswith(b"\x89PNG\r\n\x1a\n")

        if ext == "webp":
            return header.startswith(b"RIFF") and b"WEBP" in header[:16]

        if ext == "pdf":
            return header.startswith(b"%PDF")

        if ext in ["docx", "xlsx", "pptx"]:
            return header.startswith(b"PK")

        if ext == "txt":
            return True

        if ext == "mp3":
            return (
                header.startswith(b"ID3")
                or header.startswith(b"\xff\xfb")
                or header.startswith(b"\xff\xf3")
                or header.startswith(b"\xff\xf2")
            )

        if ext == "wav":
            return header.startswith(b"RIFF") and b"WAVE" in header[:16]

        if ext == "flac":
            return header.startswith(b"fLaC")

        if ext == "ogg":
            return header.startswith(b"OggS")

        if ext in ["mp4", "mov", "m4a"]:
            return b"ftyp" in header

        if ext == "avi":
            return header.startswith(b"RIFF") and b"AVI" in header[:32]

        if ext in ["webm", "mkv"]:
            return header.startswith(b"\x1A\x45\xDF\xA3")

        if ext in ["heic", "heif", "aac"]:
            return True

        return True

    except OSError:
        return False


async def cleanup_old_uploads():
    while True:
        await asyncio.sleep(900)
        now = time.time()

        try:
            for fname in os.listdir(UPLOAD_FOLDER):
                fpath = os.path.join(UPLOAD_FOLDER, fname)

                try:
                    if (
                        os.path.isfile(fpath)
                        and (now - os.path.getmtime(fpath)) > UPLOAD_TTL_SECONDS
                    ):
                        os.remove(fpath)
                        logger.info(f"Fichier supprimé : {fname}")

                except OSError as e:
                    logger.warning(f"Erreur suppression {fname} : {e}")

        except FileNotFoundError:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    asyncio.create_task(cleanup_old_uploads())
    yield


app = FastAPI(
    title="C2PA Service",
    description="Analyse le manifeste C2PA et les preuves d'authenticité",
    version="2.7.0",
    lifespan=lifespan,
)


def get_c2patool_command() -> str | None:
    if os.path.isfile(C2PATOOL_PATH) and os.access(C2PATOOL_PATH, os.X_OK):
        return C2PATOOL_PATH

    return shutil.which(C2PATOOL_PATH)


def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()

    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)

    return h.hexdigest()


def detect_media_type(ext: str) -> str:
    return ALLOWED_EXTENSIONS.get(ext, "unknown")


def run_c2patool(filepath: str) -> dict:
    result = {
        "tool_available": False,
        "has_manifest": False,
        "c2pa_certified": False,
        "certificate_trusted": None,
        "validation_status": "not_checked",
        "raw_report": None,
        "error": None,
    }

    tool_cmd = get_c2patool_command()

    if tool_cmd is None:
        result["error"] = "c2patool non installé ou C2PATOOL_PATH invalide"
        return result

    result["tool_available"] = True

    real_upload = os.path.realpath(UPLOAD_FOLDER)
    real_file = os.path.realpath(filepath)

    if not real_file.startswith(real_upload + os.sep):
        result["error"] = "Chemin de fichier non autorisé"
        result["validation_status"] = "security_error"
        return result

    try:
        process = subprocess.run(
            [tool_cmd, real_file ,"--info"],
            capture_output=True,
            text=True,
            timeout=45,
        )

        output = (process.stdout or "") + (process.stderr or "")
        lower_output = output.lower()

        result["raw_report"] = output

        manifest_keywords = [
            "manifest",
            "claim",
            "assertion",
            "content credentials",
            "c2pa",
            "active_manifest",
            "claim_generator",
        ]

        validation_valid_keywords = [
            "validated",
            "signature validated",
            "validation status: valid",
            "success",
            "claim signature valid",
            "claimsignature.validated",
            "assertion.hasheduri.match",
            "timestamp.validated",
            "timestamp message digest matched",
            "ingredient.manifest.validated",
            "ingredient hash matched",
            "hashed uri matched",
            "manifest validated",
        ]

        validation_invalid_keywords = [
            "invalid",
            "validation error",
            "signature mismatch",
            "claim signature failed",
            "failed",
            "tampered",
        ]

        certificate_untrusted_keywords = [
            "certificate untrusted",
            "signing certificate untrusted",
        ]

        if any(w in lower_output for w in manifest_keywords):
            result["has_manifest"] = True

        has_valid_signal = any(w in lower_output for w in validation_valid_keywords)
        has_invalid_signal = any(w in lower_output for w in validation_invalid_keywords)
        has_untrusted_certificate = any(
            w in lower_output for w in certificate_untrusted_keywords
        )

        result["certificate_trusted"] = not has_untrusted_certificate

        if has_valid_signal:
            result["validation_status"] = (
                "valid_but_certificate_untrusted"
                if has_untrusted_certificate
                else "valid"
            )
            result["c2pa_certified"] = True

        elif has_invalid_signal:
            result["validation_status"] = "invalid"
            result["c2pa_certified"] = False
            
        elif result["has_manifest"] and result["certificate_trusted"]:
            result["validation_status"] = "manifest_detected_trusted"
            result["c2pa_certified"] = True

        elif result["has_manifest"]:
            result["validation_status"] = "manifest_detected_not_verified"
            result["c2pa_certified"] = False

        else:
            result["validation_status"] = "no_manifest"
            result["c2pa_certified"] = False

    except subprocess.TimeoutExpired:
        result["validation_status"] = "timeout"
        result["error"] = "Timeout lors de l'exécution de c2patool"

    except Exception as e:
        result["validation_status"] = "tool_error"
        result["error"] = str(e)

    return result


def fallback_scan(filepath: str) -> dict:
    result = {
         "has_manifest": False,
         "ai_generated": False,
         "edited": False,
         "tool_used": None,
         "modifications": [],
         "details": [],
    }

    c2pa_markers = [
        b"c2pa",
        b"C2PA",
        b"contentCredentials",
        b"ContentCredentials",
        b"c2pa.assertions",
        b"c2pa.claim",
        b"claim_generator",
        b"generatedBy",
    ]

    tool_markers = {
    b"Firefly": {
        "tool": "Adobe Firefly",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec Adobe Firefly"
    },

    b"Gemini": {
        "tool": "Google Gemini",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec Google Gemini"
    },

    b"DALL-E": {
        "tool": "OpenAI DALL-E",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec DALL-E"
    },

    b"OpenAI": {
        "tool": "OpenAI",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec OpenAI"
    },

    b"Midjourney": {
        "tool": "Midjourney",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec Midjourney"
    },

    b"Stable Diffusion": {
        "tool": "Stable Diffusion",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec Stable Diffusion"
    },

    b"StableDiffusion": {
        "tool": "Stable Diffusion",
        "ai_generated": True,
        "edited": False,
        "message": "Contenu généré avec Stable Diffusion"
    },

    b"Photoshop": {
        "tool": "Adobe Photoshop",
        "ai_generated": False,
        "edited": True,
        "message": "Contenu retouché avec Adobe Photoshop"
    },

    b"Lightroom": {
        "tool": "Adobe Lightroom",
        "ai_generated": False,
        "edited": True,
        "message": "Contenu retouché avec Adobe Lightroom"
    },

    b"GIMP": {
        "tool": "GIMP",
        "ai_generated": False,
        "edited": True,
        "message": "Contenu retouché avec GIMP"
    },

   
}

    max_marker_len = max(len(m) for m in list(c2pa_markers) + list(tool_markers.keys()))

    try:
        total_read = 0
        overlap = b""

        with open(filepath, "rb") as f:
            while total_read < FALLBACK_MAX_READ:
                chunk = f.read(FALLBACK_CHUNK_SIZE)

                if not chunk:
                    break

                window = overlap + chunk

                if not result["has_manifest"]:
                    for marker in c2pa_markers:
                        if marker in window:
                            result["has_manifest"] = True
                            result["details"].append(
                                f"Indice C2PA détecté : {marker.decode(errors='ignore')}"
                            )
                            break

                for marker, info in tool_markers.items():
                        if marker in window:

                            tool = info["tool"]
                            is_ai = info["ai_generated"]
                            is_edited = info["edited"]
                            msg = info["message"]

                            if tool and not result["tool_used"]:
                                result["tool_used"] = tool

                            if is_ai:
                                result["ai_generated"] = True

                            if is_edited:
                                result["edited"] = True

                            if msg not in result["modifications"]:
                                result["modifications"].append(msg)

    except Exception as e:
        result["details"].append(f"Erreur scan local : {e}")

    if not result["details"]:
        result["details"].append("Aucun indice C2PA détecté par scan local")

    return result


def analyze_c2pa(filepath: str, filename: str, ext: str) -> dict:
    sha256 = compute_sha256(filepath)
    media_type = detect_media_type(ext)

    c2pa_tool_result = run_c2patool(filepath)
    fallback_result = fallback_scan(filepath)

    has_manifest = (
        c2pa_tool_result["has_manifest"]
        or fallback_result["has_manifest"]
    )

    c2pa_certified = c2pa_tool_result["c2pa_certified"]

    details = []

    if c2pa_tool_result["tool_available"]:
        details.append("Analyse C2PA effectuée avec c2patool")
    else:
        details.append("c2patool non disponible")

    details.extend(fallback_result["details"])

    if c2pa_certified:
        details.append("Manifeste C2PA validé techniquement")
        if c2pa_tool_result["certificate_trusted"] is False:
            details.append("Certificat détecté comme non approuvé localement")

    elif has_manifest:
        details.append("Manifeste C2PA détecté mais non validé cryptographiquement")

    else:
        details.append("Aucun manifeste C2PA valide détecté")
    
    certified = c2pa_certified
    ai_generated = fallback_result["ai_generated"]
    edited = fallback_result["edited"]

    if certified and ai_generated:
        content_origin = "ai_generated_certified"

    elif certified and edited:
        content_origin = "edited_certified"

    elif certified:
        content_origin = "certified"

    elif ai_generated:
        content_origin = "ai_generated_not_certified"

    elif edited:
        content_origin = "edited_not_certified"

    else:
        content_origin = "unknown"

    return {
        "success": True,
        "fichier": filename,
        "type_media": media_type,
        "sha256": sha256,
        "has_manifest": has_manifest,
        "c2pa_certified": c2pa_certified,
        "certificate_trusted": c2pa_tool_result["certificate_trusted"],
        "validation_status": c2pa_tool_result["validation_status"],
        "ai_generated": fallback_result["ai_generated"],
        "tool_used": fallback_result["tool_used"],
        "modifications": fallback_result["modifications"],
        "c2pa_tool_available": c2pa_tool_result["tool_available"],
        "details": details,
        "error": c2pa_tool_result["error"],
        "certified": certified,
        "edited": edited,
        "content_origin": content_origin,
    }


@app.post("/c2pa")
async def verify_c2pa(
    request: Request,
    media: UploadFile = File(...),
):
    if not media.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    ext = get_safe_extension(media.filename)

    if ext is None:
        raise HTTPException(
            status_code=415,
            detail="Extension non supportée"
        )

    content_length = request.headers.get("content-length")

    if content_length and int(content_length) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Fichier trop volumineux"
        )

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    safe_filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_FOLDER, safe_filename)

    total_written = 0

    try:
        with open(filepath, "wb") as out_file:
            while True:
                chunk = await media.read(65_536)

                if not chunk:
                    break

                total_written += len(chunk)

                if total_written > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Fichier trop volumineux"
                    )

                out_file.write(chunk)

    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)

        raise

    if not check_magic_bytes(filepath, ext):
        os.remove(filepath)

        raise HTTPException(
            status_code=422,
            detail=f"Le contenu du fichier ne correspond pas à .{ext}"
        )

    try:
        result = analyze_c2pa(filepath, media.filename, ext)
        return JSONResponse(result)

    except Exception as e:
        logger.exception("Erreur analyse C2PA")

        return JSONResponse({
            "success": False,
            "fichier": media.filename,
            "type_media": "unknown",
            "sha256": None,
            "has_manifest": False,
            "c2pa_certified": False,
            "certificate_trusted": None,
            "validation_status": "error",
            "ai_generated": False,
            "tool_used": None,
            "modifications": [],
            "c2pa_tool_available": get_c2patool_command() is not None,
            "details": [f"Erreur analyse C2PA : {e}"],
            "error": str(e),
        }, status_code=500)

    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)

        except OSError as e:
            logger.warning(f"Erreur suppression fichier : {e}")


@app.get("/")
async def home():
    return {
        "service": "c2pa_service",
        "message": "C2PA Service actif",
        "version": "2.7.0",
        "routes": {
            "health": "/health",
            "verify": "/c2pa",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    tool_path = get_c2patool_command()

    return {
        "service": "c2pa_service",
        "status": "ok",
        "port": 5004,
        "c2patool_detected": tool_path is not None,
        "c2patool_path": tool_path,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.c2pa_service:app",
        host="0.0.0.0",
        port=5004,
        reload=True,
    )