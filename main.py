# ================================================================
# FICHIER  : main.py
# ROLE     : Gateway principal — Contrôleur MVC
# ================================================================

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
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

templates = Jinja2Templates(directory="frontend/templates")
UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'webp'],
    'audio': ['mp3', 'wav'],
    'video': ['mp4', 'avi']
}

SERVICES = {
    "score": "http://localhost:5001",
    "watermark": "http://localhost:5002",
    "hash": "http://localhost:5003",
    "c2pa": "http://localhost:5004",
    "wm_video": "http://localhost:5005",
}

# ================================================================
# UTILS
# ================================================================

def get_extension(filename):
    return filename.rsplit('.', 1)[-1].lower()

def detect_media_type(filename):
    ext = get_extension(filename)
    for t, exts in ALLOWED_EXTENSIONS.items():
        if ext in exts:
            return t
    return "unknown"

def is_allowed(filename):
    return '.' in filename and detect_media_type(filename) != "unknown"

# ================================================================
# APPEL SERVICE
# ================================================================

def call_service(name, route, filepath, filename):
    try:
        url = SERVICES[name] + route
        with open(filepath, 'rb') as f:
            response = requests.post(
                url,
                files={"media": (filename, f)},
                timeout=20
            )

        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"{name} error", "available": False}

    except Exception as e:
        return {"error": str(e), "available": False}

# ================================================================
# SCORE
# ================================================================

def call_score_service(fichier, hash_res, c2pa_res, wm_res):
    try:
        url = SERVICES["score"] + "/score"

        response = requests.post(
            url,
            json={
                "fichier": fichier,
                "hash": hash_res,
                "c2pa": c2pa_res,
                "watermark": wm_res
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {"score": 0, "label": "Faible", "color": "red"}

    except Exception as e:
        return {
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
    if test_connexion():
        create_tables()
        print("MySQL OK")
    else:
        print("WAMP non lancé")

# ================================================================
# ROUTES
# ================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze(media: UploadFile = File(...)):

    if not is_allowed(media.filename):
        raise HTTPException(status_code=415, detail="Format non supporté")

    media_type = detect_media_type(media.filename)

    #  NOM UNIQUE (IMPORTANT)
    unique_name = f"{uuid.uuid4()}_{media.filename}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    # SERVICES
    hash_res = call_service("hash", "/hash", filepath, unique_name)
    c2pa_res = call_service("c2pa", "/c2pa", filepath, unique_name)

    if media_type == "image":
        wm_res = call_service("watermark", "/watermark-image/detect", filepath, unique_name)
    elif media_type == "audio":
        wm_res = call_service("watermark", "/watermark-audio/detect", filepath, unique_name)
    elif media_type == "video":
        wm_res = call_service("wm_video", "/watermark-video/detect", filepath, unique_name)
    else:
        wm_res = {}

    score_res = call_score_service(unique_name, hash_res, c2pa_res, wm_res)

    analyse_id = sauvegarder_analyse(
        fichier=unique_name,
        type_media=media_type,
        hash_result=hash_res,
        c2pa_result=c2pa_res,
        watermark_result=wm_res,
        score_result=score_res
    )

    # SUPPRESSION FICHIER TEMPORAIRE
    try:
        os.remove(filepath)
    except:
        pass

    return JSONResponse({
        "success": True,
        "id": analyse_id,
        "fichier": unique_name,
        "type": media_type,
        "hash": hash_res,
        "c2pa": c2pa_res,
        "watermark": wm_res,
        "score": score_res
    })


@app.get("/history")
async def history(request: Request):
    data = get_historique()

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("history.html", {
            "request": request,
            "analyses": data
        })

    return {"data": data}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "gateway"}

# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)