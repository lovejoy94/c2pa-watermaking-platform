# ================================================================
# FICHIER  : main.py
# ROLE     : Gateway principal — Contrôleur MVC + Microservices
# LANCER   : python -m uvicorn main:app --port 5000 --reload
# ================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import requests
import shutil
import os
import uuid
from fastapi.responses import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

from database import (
    sauvegarder_analyse,
    get_historique,
    create_tables,
    test_connexion
)

# ================================================================
# CONFIGURATION
# ================================================================

UPLOAD_FOLDER = "uploads"

ALLOWED_EXTENSIONS = {
    "image": ["jpg", "jpeg", "png", "webp"],
    "audio": ["mp3", "wav"],
    "video": ["mp4", "avi", "mov", "mkv", "webm"],
    "document": ["pdf", "docx", "xlsx", "pptx", "txt"]
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
# LIFESPAN MODERNE
# ================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("manifests", exist_ok=True)
    os.makedirs("frontend/templates", exist_ok=True)
    os.makedirs("frontend/static", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    if test_connexion():
        create_tables()
        print("MySQL OK")
    else:
        print("WAMP non lancé ou MySQL indisponible")

    yield


# ================================================================
# CRÉATION DOSSIERS AVANT APP
# ================================================================

os.makedirs("frontend/static", exist_ok=True)
os.makedirs("frontend/templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("reports", exist_ok=True)
os.makedirs("manifests", exist_ok=True)

# ================================================================
# APP
# ================================================================

app = FastAPI(
    title="C2PA Watermarking Platform",
    version="1.1.0",
    lifespan=lifespan
)

app.mount(
    "/static",
    StaticFiles(directory="frontend/static"),
    name="static"
)

templates = Jinja2Templates(directory="frontend/templates")

# ================================================================
# OUTILS
# ================================================================

def get_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower()


def detect_media_type(filename: str) -> str:
    ext = get_extension(filename)

    for media_type, extensions in ALLOWED_EXTENSIONS.items():
        if ext in extensions:
            return media_type

    return "unknown"


def is_allowed(filename: str) -> bool:
    return "." in filename and detect_media_type(filename) != "unknown"


# ================================================================
# APPEL DES MICROSERVICES
# ================================================================

def call_service(service_name: str, route: str, filepath: str, filename: str) -> dict:
    try:
        url = SERVICES[service_name] + route

        with open(filepath, "rb") as file:
            response = requests.post(
                url,
                files={"media": (filename, file)},
                timeout=45
            )

        if response.status_code == 200:
            return response.json()

        return {
            "success": False,
            "error": f"Erreur {service_name} : HTTP {response.status_code}",
            "details": response.text
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

def call_sign_service(filepath: str, filename: str) -> dict:
    try:
        url = SERVICES["hash"] + "/sign"

        with open(filepath, "rb") as file:
            response = requests.post(
                url,
                files={"media": (filename, file)},
                timeout=45
            )

        if response.status_code == 200:
            return response.json()

        return {
            "success": False,
            "signature_valid": False,
            "error": f"Erreur signature : HTTP {response.status_code}"
        }

    except Exception as e:
        return {
            "success": False,
            "signature_valid": False,
            "error": str(e)
        }
        
def call_score_service(filename: str, hash_res: dict, c2pa_res: dict, wm_res: dict, signature_res: dict) -> dict:
    try:
        url = SERVICES["score"] + "/score"

        response = requests.post(
            url,
            json={
                "fichier": filename,
                "hash": hash_res,
                "c2pa": c2pa_res,
                "watermark": wm_res,
                "signature": signature_res
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
        
def generate_pdf_report(analyse_id, filename, media_type, hash_res, c2pa_res, wm_res, score_res, signature_res):
    report_path = f"reports/rapport_{analyse_id}.pdf"

    doc = SimpleDocTemplate(report_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Rapport d'analyse d'authenticité média", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph(f"<b>Date :</b> {datetime.now().isoformat()}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Fichier :</b> {filename}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Type média :</b> {media_type}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>1. Résultat Hash SHA-256</b>", styles["Heading2"]))
    elements.append(Paragraph(f"SHA-256 : {hash_res.get('sha256', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"Fichier connu : {hash_res.get('already_known', False)}", styles["Normal"]))
    elements.append(Paragraph(f"Modifié : {hash_res.get('modified', False)}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>2. Résultat C2PA</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Manifeste détecté : {c2pa_res.get('has_manifest', False)}", styles["Normal"]))
    elements.append(Paragraph(f"C2PA certifié : {c2pa_res.get('c2pa_certified', False)}", styles["Normal"]))
    elements.append(Paragraph(f"Certificat fiable : {c2pa_res.get('certificate_trusted', None)}", styles["Normal"]))
    elements.append(Paragraph(f"Origine du contenu : {c2pa_res.get('content_origin', 'unknown')}", styles["Normal"]))
    elements.append(Paragraph(f"Outil utilisé : {c2pa_res.get('tool_used', 'Inconnu')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>3. Résultat Watermark</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Watermark détecté : {wm_res.get('watermark_found', False)}", styles["Normal"]))
    elements.append(Paragraph(f"Confiance watermark : {wm_res.get('confidence', wm_res.get('wm_confidence', 0))} %", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>4. Signature RSA</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Algorithme : {signature_res.get('signature_algorithm', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"Signé par : {signature_res.get('signed_by', 'N/A')}", styles["Normal"]))
    elements.append(Paragraph(f"Date signature : {signature_res.get('signed_at', 'N/A')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>5. Score global</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Score : {score_res.get('score', 0)} %", styles["Normal"]))
    elements.append(Paragraph(f"Niveau : {score_res.get('label', 'Faible')}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>Conclusion</b>", styles["Heading2"]))
    elements.append(Paragraph(
        "Ce rapport combine l'empreinte SHA-256, la vérification C2PA, "
        "la détection de watermark et le score global afin d'évaluer "
        "l'authenticité du média analysé.",
        styles["Normal"]
    ))

    doc.build(elements)

    return report_path


# ================================================================
# ROUTES HTML
# ================================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request):
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
@app.get("/report/{analyse_id}")
async def download_report(analyse_id: int):
    report_path = f"reports/rapport_{analyse_id}.pdf"

    if not os.path.exists(report_path):
        raise HTTPException(
            status_code=404,
            detail="Rapport PDF introuvable"
        )

    return FileResponse(
        report_path,
        media_type="application/pdf",
        filename=f"rapport_analyse_{analyse_id}.pdf"
    )
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

    if not media.filename:
        raise HTTPException(
            status_code=400,
            detail="Aucun fichier envoyé"
        )

    if not is_allowed(media.filename):
        raise HTTPException(
            status_code=415,
            detail="Format non supporté"
        )

    media_type = detect_media_type(media.filename)

    unique_name = f"{uuid.uuid4()}_{media.filename}"

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    filepath = os.path.join(
        UPLOAD_FOLDER,
        unique_name
    )

    with open(filepath, "wb") as file:
        shutil.copyfileobj(media.file, file)

    try:
        # ========================================================
        # 1. HASH SERVICE
        # ========================================================

        hash_res = call_service(
            "hash",
            "/hash",
            filepath,
            unique_name
        )
        
        signature_res = call_sign_service(
            filepath,
            unique_name
        )
        
    
        # ========================================================
        # 2. C2PA SERVICE
        # ========================================================

        c2pa_res = call_service(
            "c2pa",
            "/c2pa",
            filepath,
            unique_name
        )

        # ========================================================
        # 3. WATERMARK SERVICE
        # ========================================================

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

        # ========================================================
        # 4. SCORE SERVICE
        # ========================================================

        score_res = call_score_service(
            unique_name,
            hash_res,
            c2pa_res,
            wm_res,
            signature_res
        )

        # ========================================================
        # 5. SAUVEGARDE MYSQL
        # ========================================================

        analyse_id = sauvegarder_analyse(
            fichier=unique_name,
            type_media=media_type,
            hash_result=hash_res,
            c2pa_result=c2pa_res,
            watermark_result=wm_res,
            score_result=score_res
        )
        
        report_path = generate_pdf_report(
            analyse_id,
            unique_name,
            media_type,
            hash_res,
            c2pa_res,
            wm_res,
            score_res,
            signature_res
        )

        # ========================================================
        # 6. RÉPONSE UNIFIÉE
        # ========================================================

        return JSONResponse(
            {
            "success": True,
            "id": analyse_id,
            "report_url": f"/report/{analyse_id}",

            "fichier": unique_name,
            "type_media": media_type,
            
            # SIGNATURE RSA
            "signature_algorithm": signature_res.get("signature_algorithm", None),
            "signature": signature_res.get("signature", None),
            "signed_by": signature_res.get("signed_by", None),
            "signed_at": signature_res.get("signed_at", None),
            "signature_error": signature_res.get("error", None),

            # HASH
            "sha256": hash_res.get("sha256", ""),
            "already_known": hash_res.get("already_known", False),
            "modified": hash_res.get("modified", False),

            # C2PA
            "has_manifest": c2pa_res.get("has_manifest", False),
            "c2pa_certified": c2pa_res.get("c2pa_certified", False),
            "certificate_trusted": c2pa_res.get("certificate_trusted", None),
            "validation_status": c2pa_res.get("validation_status", "unknown"),

            # ORIGINE / IA / ÉDITION
            "ai_generated": c2pa_res.get("ai_generated", False),
            "edited": c2pa_res.get("edited", False),
            "certified": c2pa_res.get(
                "certified",
                c2pa_res.get("c2pa_certified", False)
            ),
            
            "content_origin": c2pa_res.get("content_origin", "unknown"),
            "tool_used": c2pa_res.get("tool_used", "Inconnu"),
            "modifications": c2pa_res.get("modifications", []),

            # WATERMARK
            "watermark_found": wm_res.get("watermark_found", False),
            "wm_confidence": wm_res.get("confidence", wm_res.get("wm_confidence", 0)),
            "watermark_metadata": wm_res.get("watermark_metadata", None),

            # SCORE
            "score": score_res.get("score", 0),
            "label": score_res.get("label", "Faible"),
            "color": score_res.get("color", "red"),
            "decision": score_res.get("decision", "À VÉRIFIER"),
            "risks": score_res.get("risks", []),
            "details": score_res.get("details", []),

            # RAPPORT COMPLET
            "raw": {
                "hash": hash_res,
                "c2pa": c2pa_res,
                "watermark": wm_res,
                "signature": signature_res,
                "score": score_res
            }
             
        })

    finally:
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
    return {
        "status": "ok",
        "service": "gateway",
        "architecture": "microservices",
        "port": 5000,
        "services": SERVICES
       
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