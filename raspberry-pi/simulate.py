# ============================================
#  SIMULATE.PY = TEST SANS RASPBERRY
# ============================================
# Simule le comportement du Pi depuis un PC : envoie une photo dans Storage,
# écrit un relevé "events", un passage "catSightings", les stats du jour et
# le statut. Permet de tester l'app mobile sans le matériel.
#
# Prérequis :
#   pip install firebase-admin
#   raspberry-pi/service-account.json présent (clé privée Firebase)
#
# Utilisation :
#   python simulate.py                          # gamelle pleine, sans photo perso
#   python simulate.py --state empty            # gamelle vide
#   python simulate.py --state full --cat       # gamelle pleine + chat vu
#   python simulate.py --photo C:/chemin/photo.jpg --state empty

import argparse
import base64
import io
import sys
import uuid
from datetime import datetime, timezone

import firebase_admin
from firebase_admin import credentials, firestore, storage

# Petite image JPEG de secours (carré orange) si aucune photo n'est fournie
_FALLBACK_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPDQ0NP/AABEIAAEAAQMBIgACEQEDEQH/xAAfAAAB"
    "BQAAAAAAAAAAAAAAAAAAAAUHAQIGAwEB/8QAHAAAAgMAAAAAAAAAAAAAAAAABQcBBAYCAwgH/8QA"
    "FAEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAA"
    "AAAAAAAAAAAP/aAAwDAQACEQMRAD8AKgA//9k="
)

def main():
    parser = argparse.ArgumentParser(description="Simule un relevé du Raspberry Pi")
    parser.add_argument("--state", choices=["full", "empty"], default="full",
                        help="état de la gamelle (défaut: full)")
    parser.add_argument("--photo", help="chemin d'une photo JPG à utiliser")
    parser.add_argument("--cat", action="store_true",
                        help="le chat a été vu sur la photo")
    parser.add_argument("--device", default="raspberry-pi-1")
    args = parser.parse_args()

    # 1. Connexion à Firebase avec le compte de service du Pi
    try:
        cred = credentials.Certificate("service-account.json")
    except FileNotFoundError:
        print("❌ service-account.json introuvable : place la clé privée Firebase dans raspberry-pi/")
        sys.exit(1)
    firebase_admin.initialize_app(cred, {
        "projectId": "gamelle-connectee-2e3be",
        "storageBucket": "gamelle-connectee-2e3be.firebasestorage.app",
    })
    db = firestore.client()
    bucket = storage.bucket()

    # 2. Photo à envoyer (photo perso ou carré orange)
    if args.photo:
        with open(args.photo, "rb") as f:
            photo_bytes = f.read()
    else:
        photo_bytes = base64.b64decode(_FALLBACK_JPEG_B64)
    photo_name = f"photos/{args.device}/simulate_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
    bucket.blob(photo_name).upload_from_string(photo_bytes, content_type="image/jpeg")

    # 3. Événement (comme main.py : record_event)
    bowl_empty = args.state == "empty"
    score = 18.0 if bowl_empty else 52.0  # valeurs plausibles, à titre d'exemple
    db.collection("events").add({
        "deviceId": args.device,
        "bowlEmpty": bowl_empty,
        "fillScore": score,
        "photoPath": photo_name,
        "videoPath": None,
        "catSeen": args.cat,
        "onDemand": False,
        "occluded": False,
        "timestamp": firestore.SERVER_TIMESTAMP,
    })

    # 4. Passage du chat + stats du jour + statut (comme main.py)
    if args.cat:
        db.collection("catSightings").add({
            "deviceId": args.device,
            "confidence": 0.87,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.collection("dailyStats").document(date_str).set({
        "date": date_str,
        "fullChecks": firestore.Increment(0 if bowl_empty else 1),
        "emptyChecks": firestore.Increment(1 if bowl_empty else 0),
        "catSightings": firestore.Increment(1 if args.cat else 0),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }, merge=True)
    db.collection("status").document(args.device).set({
        "cpuTemp": 42.3,
        "uptimeSeconds": 3600,
        "lastScore": score,
        "bowlEmpty": bowl_empty,
        "lastSeen": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    print(f"✅ Relevé envoyé : gamelle {'VIDE' if bowl_empty else 'pleine'}"
          f" | chat: {'oui' if args.cat else 'non'}")
    print(f"   Photo : {photo_name}")
    print("→ Relance l'app mobile, tout doit apparaître en temps réel.")

if __name__ == "__main__":
    main()
