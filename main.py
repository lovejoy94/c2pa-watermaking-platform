# ================================================================
# FICHIER  : main.py
# ROLE     : Gateway principal — Contrôleur MVC + Microservices
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import requests
import shutil
import os
import uuid

from database import sauvegarder_analyse, get_historique, create_tables, test_connexion

# ================================================================
# CONFIGURATION
# ================================================================

app = FastAPI(
    title="C2PA Watermarking Platform",
    version="1.0.0"
)

# Dossier des fichiers CSS et JS
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Dossier des pages HTML
templates = Jinja2Templates(directory="frontend/templates")

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    "image": ["jpg", "jpeg", "png", "webp"],
    "audio": ["mp3", "wav"],
    "video": ["mp4", "avi"],
    "document": ["pdf", "docx", "xlsx", "pptx","txt"]
}

SERVICES = {
    "score": "http://localhost:5001",
    "watermark": "http://localhost:5002",
    "hash": "http://localhost:5003",
    "c2pa": "http://localhost:5004",
    "wm_video": "http://localhost:5005",
    "wm_document": "http://localhost:5006",

}

# ================================================================
# OUTILS
# ================================================================

def get_extension(filename: str) -> str:
    """
    Récupère l'extension du fichier.
    Exemple : image.JPG -> jpg
    """
    return filename.rsplit(".", 1)[-1].lower()


def detect_media_type(filename: str) -> str:
    """
    Détecte le type du média : image, audio, video ou unknown.
    """
    ext = get_extension(filename)

    for media_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return media_type

    return "unknown"


def is_allowed(filename: str) -> bool:
    """
    Vérifie si le fichier possède une extension acceptée.
    """
    return "." in filename and detect_media_type(filename) != "unknown"


# ================================================================
# APPEL DES MICROSERVICES
# ================================================================

def call_service(service_name: str, route: str, filepath: str, filename: str) -> dict:
    """
    Appelle un microservice en HTTP REST.
    Le fichier est envoyé avec le champ 'media'.
    """

    try:
        url = SERVICES[service_name] + route

        with open(filepath, "rb") as file:
            response = requests.post(
                url,
                files={"media": (filename, file)},
                timeout=30
            )

        if response.status_code == 200:
            return response.json()

        return {
            "success": False,
            "error": f"Erreur {service_name} : HTTP {response.status_code}"
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": f"Service {service_name} non disponible"
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": f"Service {service_name} timeout"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def call_score_service(filename: str, hash_res: dict, c2pa_res: dict, wm_res: dict) -> dict:
    """
    Appelle le score service.
    Ici on envoie du JSON, pas un fichier.
    """

    try:
        url = SERVICES["score"] + "/score"

        response = requests.post(
            url,
            json={
                "fichier": filename,
                "hash": hash_res,
                "c2pa": c2pa_res,
                "watermark": wm_res
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

        return {
            "success": False,
            "score": 0,
            "label": "Faible",
            "color": "red",
            "details": ["Score service indisponible"]
        }

    except Exception as e:
        return {
            "success": False,
            "score": 0,
            "label": "Faible",
            "color": "red",
            "details": [str(e)]
        }


# ================================================================
# STARTUP
# ================================================================

@app.on_event("startup")
async def startup():
    """
    S'exécute au démarrage du serveur principal.
    Vérifie MySQL et crée les tables si nécessaire.
    """

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("manifests", exist_ok=True)
    os.makedirs("frontend/templates", exist_ok=True)
    os.makedirs("frontend/static", exist_ok=True)

    if test_connexion():
        create_tables()
        print("MySQL OK")
    else:
        print("WAMP non lancé ou MySQL indisponible")


# ================================================================
# ROUTES HTML
# ================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Page d'accueil.
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
    """
    Page HTML historique.
    Les données sont chargées par history.js via /api/history.
    """
    return templates.TemplateResponse(
        "history.html",
        {"request": request}
    )


@app.get("/result", response_class=HTMLResponse)
async def result_page(request: Request):
   
    return templates.TemplateResponse(
        "result.html",
        {"request": request}
    )


# ================================================================
# ROUTES API
# ================================================================

@app.get("/api/history")
async def history_api(limit: int = 50):

    try:
        data = get_historique(limit)

        return JSONResponse({
            "success": True,
            "total": len(data),
            "analyses": data
        })

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur récupération historique : {str(e)}"
        )


@app.post("/analyze")
async def analyze(media: UploadFile = File(...)):
    """
    Route principale :
    1. reçoit le média,
    2. appelle les microservices,
    3. calcule le score,
    4. sauvegarde en base,
    5. retourne les données attendues par result.js.
    """

    if not media.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier envoyé")

    if not is_allowed(media.filename):
        raise HTTPException(status_code=415, detail="Format non supporté")

    media_type = detect_media_type(media.filename)

    # Nom unique pour éviter qu'un fichier écrase un autre
    unique_name = f"{uuid.uuid4()}_{media.filename}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    # Sauvegarde temporaire du fichier
    with open(filepath, "wb") as file:
        shutil.copyfileobj(media.file, file)

    try:
        # 1. Hash service
        hash_res = call_service(
            "hash",
            "/hash",
            filepath,
            unique_name
        )

        # 2. C2PA service
        c2pa_res = call_service(
            "c2pa",
            "/c2pa",
            filepath,
            unique_name
        )

        # 3. Watermark service selon le type
        if media_type == "image":
            wm_res = call_service(
                "watermark",
                "/watermark-image/detect",
                filepath,
                unique_name
            )

        elif media_type == "audio":
            wm_res = call_service(
                "watermark",
                "/watermark-audio/detect",
                filepath,
                unique_name
            )

        elif media_type == "video":
            wm_res = call_service(
                "wm_video",
                "/watermark-video/detect",
                filepath,
                unique_name
            )
            
        elif media_type == "document":
            wm_res = call_service(
                "wm_document",
                "/watermark-document/detect",
                filepath,
                unique_name
            )

        else:
            wm_res = {
                "success": False,
                "watermark_found": False,
                "confidence": 0,
                "error": "Type média inconnu"
            }

        # 4. Score service
        score_res = call_score_service(
            unique_name,
            hash_res,
            c2pa_res,
            wm_res
        )

        # 5. Sauvegarde MySQL
        analyse_id = sauvegarder_analyse(
            fichier=unique_name,
            type_media=media_type,
            hash_result=hash_res,
            c2pa_result=c2pa_res,
            watermark_result=wm_res,
            score_result=score_res
        )

        # reponse
        return JSONResponse({
            "success": True,
            "id": analyse_id,

            "fichier": unique_name,
            "type_media": media_type,

            "sha256": hash_res.get("sha256", ""),
            "modified": hash_res.get("modified", False),

            "has_manifest": c2pa_res.get("has_manifest", False),
            "c2pa_certified": c2pa_res.get("c2pa_certified", False),
            "ai_generated": c2pa_res.get("ai_generated", False),
            
            "tool_used": c2pa_res.get("tool_used", "Inconnu"),

            "watermark_found": wm_res.get("watermark_found", False),
            "wm_confidence": wm_res.get("confidence", 0),

            "score": score_res.get("score", 0),
            "label": score_res.get("label", "Faible"),
            "color": score_res.get("color", "red"),
            "details": score_res.get("details", [])
        })

    finally:
        # Suppression du fichier temporaire
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception as e:
            print(f"Erreur suppression fichier temporaire : {e}")


# ================================================================
# HEALTH
# ================================================================

@app.get("/health")
async def health():
    """
    Vérifie que le gateway fonctionne.
    """
    return {
        "status": "ok",
        "service": "gateway",
        "architecture": "microservices",
        "port": 5000
    }


# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5000,
        reload=True
    )