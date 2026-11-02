# ============================================
#  CALIBRATE.PY = AJUSTER LA ZONE DE LA GAMELLE
# ============================================
# Capture une photo avec la webcam, dessine en vert la zone analysée
# (le "roi" de config.yaml) et publie le tout dans Storage.
# Ouvre l'URL affichée dans un navigateur : le cadre vert doit englober
# l'intérieur de la gamelle. Sinon, ajuste camera.roi dans config.yaml
# et relance.
#
# Utilisation (sur le Pi, depuis raspberry-pi/) :
#   source venv/bin/activate
#   python calibrate.py
#
# roi = [x, y, largeur, hauteur] en fractions de l'image (0.0 → 1.0).
# Exemple : la gamelle occupe le quart central → [0.25, 0.35, 0.5, 0.4]

import sys
import time

sys.path.insert(0, "src")

import cv2
import yaml
import firebase_admin
from firebase_admin import credentials, firestore, storage

from detector import BowlDetector

# --- Configuration ---
with open("config.yaml", encoding="utf-8") as f:
    config = yaml.safe_load(f)
roi = tuple(config["camera"].get("roi", (0.25, 0.35, 0.5, 0.4)))

cred = credentials.Certificate(config["firebase"]["credentials_file"])
firebase_admin.initialize_app(cred, {
    "projectId": config["firebase"]["project_id"],
    "storageBucket": config["firebase"]["storage_bucket"],
})
bucket = storage.bucket()

# --- Capture webcam ---
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH, config["camera"]["width"])
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config["camera"]["height"])
if not cap.isOpened():
    print("❌ Webcam introuvable")
    sys.exit(1)
time.sleep(2)  # stabilisation de l'exposition
ok, frame = cap.read()
cap.release()
if not ok or frame is None:
    print("❌ Échec de capture")
    sys.exit(1)

# --- Dessin de la zone ---
annotated = frame.copy()
h, w = frame.shape[:2]
rx, ry, rw, rh = roi
p1 = (int(rx * w), int(ry * h))
p2 = (int((rx + rw) * w), int((ry + rh) * h))
cv2.rectangle(annotated, p1, p2, (0, 255, 0), 3)

# --- Score de la zone (même calcul que main.py) ---
detector = BowlDetector(
    empty_threshold=config["camera"]["empty_threshold"], roi=roi)
score = detector.fill_score(frame)

# --- Publication (URL signée valable 24h) ---
blob = bucket.blob(f"calibration/{config['device']['id']}/zone_gamelle.jpg")
ok, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
blob.upload_from_string(buf.tobytes(), content_type="image/jpeg")
url = blob.generate_signed_url(version="v4", expiration=86400)

print(f"Zone actuelle : {list(roi)}")
print(f"Score de la zone : {score} (seuil \"vide\" : {detector.empty_threshold})")
print(f"Photo annotée (valable 24h) :\n{url}")
print("\n→ Le cadre vert doit englober l'intérieur de la gamelle.")
print("  Ajuste camera.roi dans config.yaml puis relance pour vérifier.")
