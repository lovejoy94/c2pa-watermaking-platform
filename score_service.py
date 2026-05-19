# ================================================================
# FICHIER  : services/score_service.py
# ROLE     : Microservice score de confiance global
# PORT     : 5001
# LANCER   : python -m uvicorn services.score_service:app --port 5001 --reload
# ================================================================

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

app = FastAPI(
    title="Score Service",
    description="Calcule un score global d'authenticité média",
    version="2.0.0"
)


# ================================================================
# MODELE REQUETE
# ================================================================

class ScoreRequest(BaseModel):
    fichier: str
    hash: Dict[str, Any]
    c2pa: Dict[str, Any]
    watermark: Dict[str, Any]
    signature: Optional[Dict[str, Any]] = None


# ================================================================
# CALCUL SCORE
# ================================================================

@app.post("/score")
async def calculate_score(data: ScoreRequest):

    score = 0
    details: List[str] = []
    risks: List[str] = []

    hash_res = data.hash or {}
    c2pa_res = data.c2pa or {}
    wm_res = data.watermark or {}
    sig_res = data.signature or {}

    # ============================================================
    # 1. HASH / INTEGRITE
    # ============================================================

    if hash_res.get("success"):
        score += 10
        details.append("Hash SHA-256 calculé avec succès")

    if hash_res.get("already_known"):
        score += 5
        details.append("Fichier déjà connu dans le registre")

    if hash_res.get("modified"):
        score -= 30
        risks.append("Le média semble avoir été modifié")

    # ============================================================
    # 2. C2PA / PROVENANCE
    # ============================================================

    if c2pa_res.get("has_manifest"):
        score += 20
        details.append("Manifeste C2PA détecté")

    if c2pa_res.get("c2pa_certified"):
        score += 25
        details.append("Manifeste C2PA certifié")

    if c2pa_res.get("certificate_trusted"):
        score += 10
        details.append("Certificat C2PA fiable")

    if c2pa_res.get("validation_status") in [
        "invalid",
        "security_error",
        "tool_error"
    ]:
        score -= 35
        risks.append("Validation C2PA problématique")

    # ============================================================
    # 3. ORIGINE IA / EDITION
    # ============================================================

    content_origin = c2pa_res.get("content_origin", "unknown")

    if content_origin == "ai_generated_certified":
        score += 10
        details.append("Contenu IA généré mais certifié")

    elif content_origin == "edited_certified":
        score += 5
        details.append("Contenu édité mais certifié")

    elif content_origin == "ai_generated_not_certified":
        score -= 10
        risks.append("Contenu IA détecté sans certification forte")

    elif content_origin == "edited_not_certified":
        score -= 10
        risks.append("Contenu édité sans certification forte")

    elif content_origin == "unknown":
        risks.append("Origine du contenu inconnue")

    # ============================================================
    # 4. WATERMARK
    # ============================================================

    if wm_res.get("watermark_found"):
        confidence = wm_res.get("confidence", 0)

        if confidence >= 80:
            score += 20
            details.append("Watermark détecté avec forte confiance")

        elif confidence >= 40:
            score += 10
            details.append("Watermark détecté avec confiance moyenne")

        else:
            score += 5
            details.append("Watermark détecté avec faible confiance")

    else:
        risks.append("Aucun watermark détecté")

    # ============================================================
    # 5. SIGNATURE RSA GROUPE 7
    # ============================================================

    if sig_res.get("success") and sig_res.get("signature"):
        score += 15
        details.append("Média signé par la plateforme Groupe 7")

    if sig_res.get("signature_valid"):
        score += 20
        details.append("Signature RSA vérifiée avec succès")

    if sig_res.get("success") is False:
        risks.append("Signature RSA absente ou non vérifiée")

    # ============================================================
    # NORMALISATION
    # ============================================================

    score = max(0, min(score, 100))

    if score >= 85:
        label = "Très fiable"
        color = "green"
        decision = "AUTHENTIQUE / CERTIFIÉ"

    elif score >= 65:
        label = "Fiable"
        color = "blue"
        decision = "PROBABLEMENT AUTHENTIQUE"

    elif score >= 40:
        label = "Moyen"
        color = "orange"
        decision = "À VÉRIFIER"

    else:
        label = "Faible"
        color = "red"
        decision = "NON FIABLE / SUSPECT"

    return {
        "success": True,
        "fichier": data.fichier,
        "score": score,
        "label": label,
        "color": color,
        "decision": decision,
        "details": details,
        "risks": risks
    }


# ================================================================
# HEALTH
# ================================================================

@app.get("/health")
async def health():
    return {
        "service": "score_service",
        "status": "ok",
        "port": 5001,
        "version": "2.0.0"
    }


# ================================================================
# RUN
# ================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.score_service:app",
        host="0.0.0.0",
        port=5001,
        reload=True
    )