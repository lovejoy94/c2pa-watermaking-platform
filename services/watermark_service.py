"""
=============================================================================
FICHIER  : services/watermark_service.py
ROLE     : Microservice de watermarking image et audio
PORT     : 5002
LANCER   : python -m uvicorn services.watermark_service:app --port 5002 --reload
AUTEUR   : Groupe 7 - C2PA Platform
=============================================================================
CONVENTIONS RESPECTÉES :
- Champ upload : media
- Champs JSON : success, fichier, type_media, watermark_found, wm_confidence, score, label, color, details, date_analyse
- Nommage : snake_case pour fonctions/variables, PascalCase pour classes, MAJUSCULES pour constantes
=============================================================================
"""

# ================================================================
# IMPORTS
# ================================================================
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import os
import json
import uuid
import shutil
import hashlib

# ------------------------------------------------------------------
# Import optionnel : mutagen (métadonnées audio)
# ------------------------------------------------------------------
try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TXXX
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    MUTAGEN_OK = True  # constante : indique si mutagen est disponible
except ImportError:
    MUTAGEN_OK = False

# ------------------------------------------------------------------
# Import optionnel : OpenCV + numpy (détection LSB image)
# ------------------------------------------------------------------
try:
    import numpy as np
    import cv2
    OPENCV_OK = True  # constante : indique si OpenCV est disponible
except ImportError:
    OPENCV_OK = False

# ================================================================
# APPLICATION FASTAPI
# ================================================================
app = FastAPI(
    title="Watermark Service",
    description="Détecte et applique le watermark audio et image - Groupe 7",
    version="1.0.0"
)

# ================================================================
# CONSTANTES (dossiers de stockage)
# ================================================================
UPLOAD_FOLDER = "uploads"     # dossier pour les fichiers uploadés temporaires
OUTPUT_FOLDER = "outputs"     # dossier pour les fichiers watermarkés finaux


# ================================================================
# FONCTIONS UTILITAIRES
# ================================================================

def safe_cleanup(*paths: str) -> None:
    """
    Supprime proprement une liste de fichiers temporaires.
    Capture les erreurs pour éviter de bloquer l'exécution.
    
    Args:
        *paths: chemins des fichiers à supprimer
    """
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[CLEANUP] Impossible de supprimer {path}: {e}")


def generate_manifest(media_type: str) -> dict:
    """
    Génère un manifeste C2PA standard avec ID unique et hash.
    
    Args:
        media_type: type de média ('audio' ou 'image')
    
    Returns:
        dict: manifeste C2PA avec manifest_id, creator, created_date, media_type
    """
    manifest = {
        "manifest_id": "c2pa-" + hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8],
        "creator": "C2PA-Service-Groupe7",
        "created_date": datetime.now().isoformat(),
        "media_type": media_type
    }
    return manifest


def calculate_hash(filepath: str) -> str:
    """
    Calcule le hash SHA-256 d'un fichier.
    
    Args:
        filepath: chemin du fichier
    
    Returns:
        str: hash hexadécimal
    """
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ================================================================
# SECTION AUDIO
# ================================================================

def apply_audio_watermark(input_path: str, output_path: str) -> str:
    """
    Applique un watermark invisible C2PA sur un fichier audio.
    
    - Si mutagen est disponible : injecte les métadonnées dans les tags ID3 (MP3) ou VorbisComment (FLAC/OGG)
    - Sinon : copie simple du fichier
    - Dans tous les cas : crée un fichier .c2pa.json avec le manifeste
    
    Args:
        input_path: chemin du fichier audio source
        output_path: chemin du fichier de sortie
    
    Returns:
        str: chemin du fichier watermarké
    """
    # Création du manifeste C2PA
    manifest = generate_manifest("audio")
    manifest["file_hash"] = calculate_hash(input_path)
    manifest_json = json.dumps(manifest, ensure_ascii=False)

    # Si mutagen n'est pas installé, copie simple
    if not MUTAGEN_OK:
        shutil.copy2(input_path, output_path)
    else:
        ext = os.path.splitext(input_path)[1].lower()
        try:
            # MP3 : utilisation des tags ID3
            if ext == ".mp3":
                audio = MP3(input_path)
                if audio.tags is None:
                    audio.tags = ID3()
                audio.tags.add(TIT2(encoding=3, text=f"C2PA-{manifest['manifest_id'][:8]}"))
                audio.tags.add(TPE1(encoding=3, text=manifest["creator"]))
                audio.tags.add(TXXX(encoding=3, desc="C2PA_METADATA", text=manifest_json))
                audio.save(output_path)

            # FLAC / OGG : utilisation des VorbisComment
            elif ext in [".flac", ".ogg"]:
                audio = FLAC(input_path) if ext == ".flac" else OggVorbis(input_path)
                audio["C2PA_METADATA"] = manifest_json
                audio.save(output_path)

            # Autres formats : copie simple
            else:
                shutil.copy2(input_path, output_path)

        except Exception:
            # En cas d'erreur, copie simple
            shutil.copy2(input_path, output_path)

    # Sauvegarde toujours le manifeste JSON externe (vérifiable)
    with open(output_path + ".c2pa.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return output_path


def verify_audio_watermark(filepath: str, fichier: str) -> dict:
    """
    Vérifie si un fichier audio contient un watermark C2PA.
    
    Vérifie d'abord le fichier .c2pa.json externe,
    puis les métadonnées internes (tags ID3 ou VorbisComment).
    
    Args:
        filepath: chemin du fichier à analyser
        fichier: nom original du fichier
    
    Returns:
        dict: résultat avec les champs officiels (success, fichier, type_media, watermark_found, wm_confidence, score, label, color, details, date_analyse)
    """
    # Initialisation du résultat avec les champs officiels
    result = {
        "success": True,
        "fichier": fichier,
        "type_media": "audio",
        "watermark_found": False,
        "wm_confidence": 0,
        "score": 0,
        "label": "Non vérifié",
        "color": "red",
        "details": [],
        "date_analyse": datetime.now().isoformat()
    }

    try:
        # Vérification 1 : fichier .c2pa.json externe
        json_path = filepath + ".c2pa.json"
        if os.path.exists(json_path):
            result["watermark_found"] = True
            result["wm_confidence"] = 100
            result["score"] = 100
            result["label"] = "Vérifié"
            result["color"] = "green"
            result["details"].append("Manifeste C2PA audio détecté (fichier .c2pa.json)")
            return result

        # Si mutagen n'est pas disponible, on s'arrête ici
        if not MUTAGEN_OK:
            result["details"].append("Bibliothèque Mutagen non installée, vérification limitée")
            return result

        ext = os.path.splitext(filepath)[1].lower()

        # Vérification 2 : tags ID3 pour MP3
        if ext == ".mp3":
            audio = MP3(filepath)
            if audio.tags and "TXXX:C2PA_METADATA" in audio.tags:
                result["watermark_found"] = True
                result["wm_confidence"] = 90
                result["score"] = 90
                result["label"] = "Vérifié"
                result["color"] = "green"
                result["details"].append("Watermark C2PA détecté dans les métadonnées MP3")

        # Vérification 3 : VorbisComment pour FLAC/OGG
        elif ext in [".flac", ".ogg"]:
            audio = FLAC(filepath) if ext == ".flac" else OggVorbis(filepath)
            if "C2PA_METADATA" in audio:
                result["watermark_found"] = True
                result["wm_confidence"] = 90
                result["score"] = 90
                result["label"] = "Vérifié"
                result["color"] = "green"
                result["details"].append("Watermark C2PA détecté dans les métadonnées")

        # Si rien trouvé
        if not result["watermark_found"]:
            result["details"].append("Aucun watermark C2PA audio détecté")

    except Exception as e:
        result["success"] = False
        result["score"] = 0
        result["label"] = "Erreur"
        result["color"] = "orange"
        result["details"].append(f"Erreur analyse audio : {str(e)}")

    return result


# ================================================================
# SECTION IMAGE
# ================================================================

def apply_image_watermark(input_path: str, output_path: str) -> str:
    """
    Applique un watermark visible (texte) + invisible (JSON C2PA) sur une image.
    
    - Dessine un rectangle blanc semi-transparent en bas à droite
    - Écrit "VERIFIE C2PA" en vert
    - Crée un fichier .c2pa.json avec le manifeste
    
    Args:
        input_path: chemin de l'image source
        output_path: chemin de l'image de sortie
    
    Returns:
        str: chemin de l'image watermarkée
    """
    # Ouverture de l'image en mode RGBA (gère la transparence)
    img = Image.open(input_path).convert("RGBA")
    
    # Création d'un calque transparent pour le texte
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # Chargement de la police (avec fallbacks)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
        except:
            font = ImageFont.load_default()

    # Texte à afficher
    text = "VERIFIE C2PA"
    
    # Calcul des dimensions du texte
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]  # largeur du texte
    th = bbox[3] - bbox[1]  # hauteur du texte
    
    # Position en bas à droite avec marge de 20px
    x = img.width - tw - 20
    y = img.height - th - 20

    # Dessin du rectangle blanc semi-transparent derrière le texte
    draw.rectangle([x-10, y-10, x+tw+10, y+th+10], fill=(255, 255, 255, 180))
    
    # Dessin du texte en vert
    draw.text((x, y), text, fill=(0, 150, 0, 255), font=font)

    # Fusion du calque avec l'image originale
    result = Image.alpha_composite(img, overlay)
    result = result.convert("RGB")  # Conversion pour sauvegarde
    result.save(output_path, quality=95)

    # Création du manifeste C2PA
    manifest = generate_manifest("image")
    manifest["file_hash"] = calculate_hash(input_path)
    
    # Sauvegarde du manifeste JSON
    with open(output_path + ".c2pa.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return output_path


def verify_image_watermark(filepath: str, fichier: str) -> dict:
    """
    Vérifie si une image contient un watermark C2PA.
    
    Utilise l'analyse LSB (Least Significant Bit) pour détecter
    des anomalies dans le canal bleu de l'image.
    
    Args:
        filepath: chemin de l'image à analyser
        fichier: nom original du fichier
    
    Returns:
        dict: résultat avec les champs officiels
    """
    # Initialisation du résultat avec les champs officiels
    result = {
        "success": True,
        "fichier": fichier,
        "type_media": "image",
        "watermark_found": False,
        "wm_confidence": 0,
        "score": 0,
        "label": "Non vérifié",
        "color": "red",
        "details": [],
        "date_analyse": datetime.now().isoformat()
    }

    # Vérification que OpenCV/numpy sont disponibles
    if not OPENCV_OK:
        result["success"] = False
        result["label"] = "Erreur"
        result["color"] = "orange"
        result["details"].append("OpenCV (cv2) ou numpy non installé, vérification LSB impossible")
        return result

    try:
        # Lecture de l'image avec OpenCV
        img = cv2.imread(filepath)
        
        # Vérification que l'image est valide
        if img is None or img.size == 0:
            result["success"] = False
            result["label"] = "Erreur"
            result["color"] = "orange"
            result["details"].append("Image vide ou illisible")
            return result

        # Analyse LSB : extraction du bit de poids faible du canal bleu
        blue = img[:, :, 0]        # canal bleu
        lsb = blue & 1             # extraction du LSB (0 ou 1)
        ratio = float(np.sum(lsb)) / lsb.size  # proportion de 1

        # Un ratio proche de 0.5 indique une distribution aléatoire (normale)
        # Un écart significatif indique une modification (watermark)
        if abs(ratio - 0.5) > 0.01:
            result["watermark_found"] = True
            result["wm_confidence"] = min(100, round(abs(ratio - 0.5) * 200))
            result["score"] = result["wm_confidence"]
            result["label"] = "Suspect"
            result["color"] = "orange"
            result["details"].append(f"Watermark LSB détecté dans le canal bleu (ratio={ratio:.4f})")
        else:
            result["label"] = "Normal"
            result["color"] = "green"
            result["details"].append(f"Aucune anomalie LSB détectée (ratio={ratio:.4f})")

    except Exception as e:
        result["success"] = False
        result["label"] = "Erreur"
        result["color"] = "orange"
        result["details"].append(f"Erreur analyse image : {str(e)}")

    return result


# ================================================================
# ROUTES API - AUDIO
# ================================================================

@app.post("/watermark-audio/detect")
async def detect_audio(media: UploadFile = File(...)):
    """
    Détecte la présence d'un watermark C2PA dans un fichier audio.
    
    - Reçoit un fichier audio via le champ 'media'
    - Analyse les métadonnées et le fichier .c2pa.json associé
    - Retourne un rapport structuré avec les champs officiels
    """
    # Validation du fichier
    if not media.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier envoyé")

    # Création du dossier d'upload
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Sauvegarde temporaire avec nom unique (évite les collisions)
    unique_name = f"{uuid.uuid4()}_{media.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    try:
        # Appel de la fonction de vérification
        result = verify_audio_watermark(filepath, media.filename)
        return JSONResponse(result)
    finally:
        # Nettoyage des fichiers temporaires
        safe_cleanup(filepath, filepath + ".c2pa.json")


@app.post("/watermark-audio/add")
async def add_audio(media: UploadFile = File(...)):
    """
    Applique un watermark C2PA invisible sur un fichier audio.
    
    - Reçoit un fichier audio via le champ 'media'
    - Injecte les métadonnées C2PA dans les tags ID3/VorbisComment
    - Crée un fichier .c2pa.json avec le manifeste
    - Sauvegarde le fichier watermarké dans le dossier outputs/
    """
    # Validation du fichier
    if not media.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier envoyé")

    # Création des dossiers
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Sauvegarde temporaire
    unique_name = f"{uuid.uuid4()}_{media.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    output_path = os.path.join(OUTPUT_FOLDER, "wm_" + media.filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    try:
        # Application du watermark
        apply_audio_watermark(filepath, output_path)

        return JSONResponse({
            "success": True,
            "fichier": media.filename,
            "type_media": "audio",
            "output": output_path,
            "date_analyse": datetime.now().isoformat()
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "fichier": media.filename,
            "type_media": "audio",
            "output": None,
            "details": [str(e)],
            "date_analyse": datetime.now().isoformat()
        }, status_code=500)

    finally:
        # Nettoyage du fichier temporaire
        safe_cleanup(filepath)


# ================================================================
# ROUTES API - IMAGE
# ================================================================

@app.post("/watermark-image/detect")
async def detect_image(media: UploadFile = File(...)):
    """
    Détecte la présence d'un watermark C2PA dans une image.
    
    - Reçoit une image via le champ 'media'
    - Analyse LSB (Least Significant Bit) du canal bleu
    - Retourne un rapport structuré avec les champs officiels
    """
    # Validation du fichier
    if not media.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier envoyé")

    # Création du dossier d'upload
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Sauvegarde temporaire
    unique_name = f"{uuid.uuid4()}_{media.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    try:
        # Appel de la fonction de vérification
        result = verify_image_watermark(filepath, media.filename)
        return JSONResponse(result)
    finally:
        # Nettoyage
        safe_cleanup(filepath)


@app.post("/watermark-image/add")
async def add_image(media: UploadFile = File(...)):
    """
    Applique un watermark visible + invisible sur une image.
    
    - Reçoit une image via le champ 'media'
    - Dessine "VERIFIE C2PA" en bas à droite (vert sur fond blanc)
    - Crée un fichier .c2pa.json avec le manifeste
    - Sauvegarde dans le dossier outputs/
    """
    # Validation du fichier
    if not media.filename:
        raise HTTPException(status_code=400, detail="Aucun fichier envoyé")

    # Création des dossiers
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    # Sauvegarde temporaire
    unique_name = f"{uuid.uuid4()}_{media.filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_name)
    output_path = os.path.join(OUTPUT_FOLDER, "wm_" + media.filename)

    with open(filepath, "wb") as f:
        shutil.copyfileobj(media.file, f)

    try:
        # Application du watermark
        apply_image_watermark(filepath, output_path)

        return JSONResponse({
            "success": True,
            "fichier": media.filename,
            "type_media": "image",
            "output": output_path,
            "date_analyse": datetime.now().isoformat()
        })

    except Exception as e:
        return JSONResponse({
            "success": False,
            "fichier": media.filename,
            "type_media": "image",
            "output": None,
            "details": [str(e)],
            "date_analyse": datetime.now().isoformat()
        }, status_code=500)

    finally:
        # Nettoyage
        safe_cleanup(filepath)


# ================================================================
# HEALTH CHECK
# ================================================================

@app.get("/health")
async def health():
    """
    Endpoint de santé du service.
    Retourne le statut et le port.
    """
    return {
        "service": "watermark_service",
        "status": "ok",
        "port": 5002
    }


# ================================================================
# LANCEMENT DIRECT
# ================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "services.watermark_service:app",
        host="0.0.0.0",
        port=5002,
        reload=True
    )
