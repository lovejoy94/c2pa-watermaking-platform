# ================================================================
# FICHIER  : services/score_service.py
# ROLE     : Calcule le score de confiance final (0 à 100)
# AUTEUR   : Chef de projet — Groupe 7
# PORT     : 5001
# LANCER   : uvicorn services.score_service:app --port 5001 --reload
# TESTER   : http://localhost:5001/docs
# ================================================================

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn

# ================================================================
# CONFIGURATION
# ================================================================

app = FastAPI(
    title="Score Service",
    description="Calcule le score de confiance d'un média analysé",
    version="1.0.0"
)

# ================================================================
# MODÈLES DE DONNÉES (Pydantic)
# ================================================================

class HashResult(BaseModel):
    """
    Résultat du hash_service
    """
    success: bool = False
    sha256: str = ""
    already_known: bool = False
    modified: bool = False
    error: Optional[str] = None


class C2PAResult(BaseModel):
    """
    Résultat du c2pa_service
    """
    success: bool = False
    has_manifest: bool = False
    certified: bool = False
    ai_generated: bool = False
    modifications: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class WatermarkResult(BaseModel):
    """
    Résultat du watermark_service
    """
    success: bool = False
    watermark_found: bool = False
    confidence: int = 0
    error: Optional[str] = None


class AnalysisRequest(BaseModel):
    """
    Données envoyées par main.py
    """
    fichier: str
    hash: HashResult
    c2pa: C2PAResult
    watermark: WatermarkResult


# ================================================================
# CALCUL DU SCORE
# ================================================================

def calculer_score(hash_res, c2pa_res, wm_res):
    """
    Barème :

    Hash valide           → +40
    C2PA certifié         → +35
    C2PA présent          → +20
    Watermark détecté     → +25
    """

    score = 0
    details = []

    # ================= HASH =================
    if hash_res.error:
        details.append("Hash indisponible (0pt)")
    elif not hash_res.modified:
        score += 40
        details.append("Hash valide (+40pts)")
    else:
        details.append("Fichier modifié (0pt)")

    # ================= C2PA =================
    if c2pa_res.error:
        details.append("C2PA indisponible (0pt)")
    elif c2pa_res.has_manifest and c2pa_res.certified:
        score += 35
        details.append("C2PA certifié (+35pts)")
    elif c2pa_res.has_manifest:
        score += 20
        details.append("C2PA présent non certifié (+20pts)")
    else:
        details.append("Pas de C2PA (0pt)")

    # ================= WATERMARK =================
    if wm_res.error:
        details.append("Watermark indisponible (0pt)")
    elif wm_res.watermark_found:
        score += 25
        details.append("Watermark détecté (+25pts)")
    else:
        details.append("Pas de watermark (0pt)")

    # ================= SCORE FINAL =================
    score = max(0, min(100, score))

    if score >= 70:
        label = "Fiable"
        color = "green"
    elif score >= 40:
        label = "Douteux"
        color = "orange"
    else:
        label = "Faible"
        color = "red"

    return {
        "score": score,
        "label": label,
        "color": color,
        "details": details
    }


# ================================================================
# ROUTES
# ================================================================

@app.post("/score")
async def calculate_score(data: AnalysisRequest):
    """
    Route principale :
    reçoit les résultats et retourne le score
    """

    result = calculer_score(data.hash, data.c2pa, data.watermark)

    return JSONResponse({
        "success": True,
        "fichier": data.fichier,
        "score": result["score"],
        "label": result["label"],
        "color": result["color"],
        "details": result["details"]
    })


@app.get("/health")
async def health():
    """
    Vérifie que le service fonctionne
    """
    return {
        "service": "score_service",
        "status": "ok",
        "port": 5001
    }


# ================================================================
# LANCEMENT
# ================================================================

if __name__ == "__main__":

    print("=" * 45)
    print(" Score Service démarré")
    print(" URL  : http://localhost:5001")
    print(" Docs : http://localhost:5001/docs")
    print("=" * 45)

    uvicorn.run(
        "services.score_service:app",
        host="0.0.0.0",
        port=5001,
        reload=True
    )