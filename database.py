# ================================================================
# FICHIER  : database.py
# ROLE     : Connexion MySQL + sauvegarde des résultats d'analyse
# ================================================================

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import json

# ================================================================
# CONFIGURATION MYSQL (WAMP)
# ================================================================

DB_USER     = "root"
DB_PASSWORD = ""  # ⚠️ vide en local seulement (WAMP)
DB_HOST     = "localhost"
DB_PORT     = "3306"
DB_NAME     = "c2paPlatform"  # ✔ TON NOM DE BASE

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ================================================================
# CONNEXION
# ================================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

Base = declarative_base()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# ================================================================
# TABLE
# ================================================================

class Verification(Base):

    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    fichier    = Column(String(255), nullable=False)
    type_media = Column(String(50), nullable=True)

    sha256   = Column(String(64), nullable=True)
    modified = Column(Boolean, default=False)

    has_manifest = Column(Boolean, default=False)
    certified    = Column(Boolean, default=False)
    ai_generated = Column(Boolean, default=False)

    watermark_found = Column(Boolean, default=False)
    wm_confidence   = Column(Integer, default=0)

    score   = Column(Integer, nullable=False)
    label   = Column(String(20), nullable=False)
    color   = Column(String(10), nullable=False)
    details = Column(Text, nullable=True)

    date_analyse = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Verification fichier={self.fichier} score={self.score}>"

# ================================================================
# INITIALISATION
# ================================================================

def create_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Tables créées avec succès")
        return True
    except Exception as e:
        print(f"Erreur création tables : {e}")
        return False


def test_connexion():
    try:
        conn = engine.connect()
        conn.close()
        print("Connexion MySQL OK")
        return True
    except Exception as e:
        print(f"Erreur connexion : {e}")
        return False

# ================================================================
# SAUVEGARDE
# ================================================================

def sauvegarder_analyse(
    fichier,
    type_media,
    hash_result,
    c2pa_result,
    watermark_result,
    score_result
):
    db = SessionLocal()
    try:
        verification = Verification(
            fichier=fichier,
            type_media=type_media,

            sha256=hash_result.get("sha256", ""),
            modified=hash_result.get("modified", False),

            has_manifest=c2pa_result.get("has_manifest", False),
            certified=c2pa_result.get("certified", False),
            ai_generated=c2pa_result.get("ai_generated", False),

            watermark_found=watermark_result.get("watermark_found", False),
            wm_confidence=watermark_result.get("confidence", 0),

            score=score_result.get("score", 0),
            label=score_result.get("label", "Faible"),
            color=score_result.get("color", "red"),

            details=json.dumps(score_result.get("details", []), ensure_ascii=False),

            date_analyse=datetime.utcnow()
        )

        db.add(verification)
        db.commit()
        db.refresh(verification)

        print(f"Analyse sauvegardée ID={verification.id}")
        return verification.id

    except Exception as e:
        db.rollback()
        print(f"Erreur sauvegarde : {e}")
        return None

    finally:
        db.close()

# ================================================================
# HISTORIQUE
# ================================================================

def get_historique(limite=50):
    db = SessionLocal()
    try:
        analyses = db.query(Verification)\
            .order_by(Verification.date_analyse.desc())\
            .limit(limite)\
            .all()

        return [
            {
                "id": a.id,
                "fichier": a.fichier,
                "type_media": a.type_media,
                "sha256": a.sha256,
                "has_manifest": a.has_manifest,
                "certified": a.certified,
                "watermark_found": a.watermark_found,
                "score": a.score,
                "label": a.label,
                "color": a.color,
                "details": json.loads(a.details) if a.details else [],
                "date_analyse": a.date_analyse.strftime("%Y-%m-%d %H:%M:%S")
            }
            for a in analyses
        ]

    except Exception as e:
        print(f"Erreur historique : {e}")
        return []

    finally:
        db.close()

# ================================================================
# TEST
# ================================================================

if __name__ == "__main__":

    print("=" * 40)
    print(" TEST DATABASE")
    print("=" * 40)

    if test_connexion():
        create_tables()
        print("Base prête")
    else:
        print("Démarre WAMP !")