# ================================================================
# FICHIER  : services/score_service.py
# ROLE     : Microservice de calcul du score de confiance
# PORT     : 5001
# LANCER   : python -m uvicorn services.score_service:app --port 5001 --reload
# ================================================================

from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, List

app = FastAPI(
    title="Score Service",
    description="Calcule le score de confiance d'un média",
    version="1.0.0"
)

# ================================================================
# MODELES REÇUS DEPUIS main.py
# ================================================================

class HashResult(BaseModel):
    success: bool = False
    sha256: str = ""
    modified: bool = False
    error: Optional[str] = None


class C2PAResult(BaseModel):
    success: bool = False
    has_manifest: bool = False
    c2pa_certified: bool = False      
    ai_generated: bool = False
    modifications: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class WatermarkResult(BaseModel):
    success: bool = False
    watermark_found: bool = False
    confidence: int = 0
    error: Optional[str] = None


class ScoreRequest(BaseModel):
    fichier: str
    hash: HashResult
    c2pa: C2PAResult
    watermark: WatermarkResult


# ================================================================
# LOGIQUE DU SCORE
# ================================================================

def calculer_score(hash_res: HashResult, c2pa_res: C2PAResult, wm_res: WatermarkResult):
    score = 0
    details = []

    # HASH : 40 points
    if hash_res.error:
        details.append("Hash indisponible (0 pt)")
    elif not hash_res.modified:
        score += 40
        details.append("Hash valide : fichier non modifié (+40 pts)")
    else:
        details.append("Hash invalide : fichier modifié (0 pt)")

    # C2PA : 35 points
    if c2pa_res.error:
        details.append("C2PA indisponible (0 pt)")
    elif c2pa_res.has_manifest and c2pa_res.c2pa_certified:   # ✅ corrigé
        score += 35
        details.append("Manifeste C2PA certifié (+35 pts)")
    elif c2pa_res.has_manifest:
        score += 20
        details.append("Manifeste C2PA présent mais non certifié (+20 pts)")
    else:
        details.append("Aucun manifeste C2PA détecté (0 pt)")

    # WATERMARK : 25 points
    if wm_res.error:
        details.append("Watermark indisponible (0 pt)")
    elif wm_res.watermark_found:
        score += 25
        details.append("Watermark détecté (+25 pts)")
    else:
        details.append("Aucun watermark détecté (0 pt)")

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
async def score_endpoint(data: ScoreRequest):
    result = calculer_score(data.hash, data.c2pa, data.watermark)
    return {
        "success": True,
        "fichier": data.fichier,
        "score":   result["score"],
        "label":   result["label"],
        "color":   result["color"],
        "details": result["details"]
    }


@app.get("/health")
async def health():
    return {
        "service": "score_service",
        "status":  "ok",
        "port":    5001
    }