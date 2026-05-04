# ================================================================
# FICHIER : shared/contrat.py
# ROLE    : Dictionnaire commun de tout le groupe
#           Chaque membre DOIT retourner exactement ces champs
#           NE PAS changer les noms des champs
# ================================================================


# ----------------------------------------------------------------
# NGOUDA — watermark_image.py
# Route : POST http://localhost:5002/watermark-image/detect
# ----------------------------------------------------------------
WATERMARK_IMAGE = {
    "success"         : True,       # le service a marché ?
    "fichier"         : "photo.jpg",# nom du fichier
    "watermark_found" : False,      # watermark trouvé ?
    "confidence"      : 0,          # score 0 à 100
    "details"         : [],         # liste de messages
    "error"           : None        # None si pas d'erreur
}


# ----------------------------------------------------------------
# NGOUDA— watermark_audio.py
# Route : POST http://localhost:5002/watermark-audio/detect
# ----------------------------------------------------------------
WATERMARK_AUDIO = {
    "success"         : True,
    "fichier"         : "son.mp3",
    "watermark_found" : False,
    "confidence"      : 0,
    "details"         : [],
    "error"           : None
}


# ----------------------------------------------------------------
# YOPA  — hash_service.py
# Route : POST http://localhost:5003/hash
# ----------------------------------------------------------------
HASH = {
    "success"      : True,
    "fichier"      : "photo.jpg",
    "sha256"       : "abc123...", # empreinte SHA-256
    "already_known": False,       # fichier déjà vu avant ?
    "modified"     : False,       # fichier modifié ?
    "status"       : "Nouveau fichier enregistré",
    "error"        : None
}


# ----------------------------------------------------------------
# YOPA— c2pa_service.py
# Route : POST http://localhost:5004/c2pa
# ----------------------------------------------------------------
C2PA = {
    "success"      : True,
    "fichier"      : "photo.jpg",
    "has_manifest" : False,  # manifeste C2PA présent ?
    "certified"    : False,  # manifeste certifié ?
    "tool_used"    : None,   # "Adobe" / "Midjourney" / None
    "ai_generated" : False,  # généré par IA ?
    "modifications": [],     # liste des modifications
    "details"      : "",
    "error"        : None
}


# ----------------------------------------------------------------
# YOPA — watermark_video.py
# Route : POST http://localhost:5005/watermark-video/detect
# ----------------------------------------------------------------
WATERMARK_VIDEO = {
    "success"               : True,
    "fichier"               : "video.mp4",
    "watermark_found"       : False,
    "confidence"            : 0,
    "frames_analyzed"       : 0,  # combien de frames analysées
    "frames_with_watermark" : 0,  # combien ont un watermark
    "details"               : [],
    "error"                 : None
}


# ================================================================
# PORTS OFFICIELS — NE JAMAIS CHANGER
# ================================================================
PORTS = {
    "gateway"         : 5000,  # main.py           — NZALI
    "score"           : 5001,  # score_service.py  — NZALI
    "watermark"       : 5002,  # watermark_*.py    — NGOUDA
    "hash"            : 5003,  # hash_service.py   — YOPA
    "c2pa"            : 5004,  # c2pa_service.py   — YOPA
    "watermark_video" : 5005,  # watermark_video   — YOPA
}


# ================================================================
# ROUTES OFFICIELLES — NE JAMAIS CHANGER
# ================================================================
ROUTES = {
    "hash"             : "/hash",
    "c2pa"             : "/c2pa",
    "watermark_image"  : "/watermark-image/detect",
    "watermark_audio"  : "/watermark-audio/detect",
    "watermark_video"  : "/watermark-video/detect",
    "score"            : "/score",
    "health"           : "/health",
}