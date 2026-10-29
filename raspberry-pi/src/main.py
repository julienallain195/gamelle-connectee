# ============================================
#  MAIN.PY = CŒUR DU PROGRAMME (boucle principale)
# ============================================
# Ce script tourne en boucle sur le Raspberry :
# 1. Prend une photo avec la caméra
# 2. Analyse si la gamelle est vide
# 3. Envoie la photo + l'info à Firebase
# 4. Envoie une notification push si gamelle vide

import time
import schedule
import yaml

from camera import Camera
from detector import BowlDetector
from firebase_client import FirebaseClient
from notifier import PushNotifier

def load_config(path="config.yaml"):
    """Lit le fichier de configuration config.yaml"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def main():
    config = load_config()

    # Initialisation des 4 composants
    camera = Camera(width=config["camera"]["width"], height=config["camera"]["height"])
    detector = BowlDetector(empty_threshold=config["camera"]["empty_threshold"])
    firebase = FirebaseClient(
        credentials_file=config["firebase"]["credentials_file"],
        project_id=config["firebase"]["project_id"],
        storage_bucket=config["firebase"]["storage_bucket"],
    )
    notifier = PushNotifier(
        expo_push_token=config["notifications"]["expo_push_token"],
        cooldown_minutes=config["notifications"]["alert_cooldown_minutes"],
    )
    device_id = config["device"]["id"]
    interval = config["camera"]["check_interval_seconds"]

    print(f"🐱 Surveillance démarrée (toutes les {interval}s)")

    def check_bowl():
        """Une vérification complète : photo → détection → Firebase → notif"""
        try:
            # 1. Prendre une photo
            image = camera.capture_array()
            # 2. Analyser : la gamelle est-elle vide ?
            bowl_empty, score = detector.is_empty(image)
            print(f"Score: {score} → {'VIDE' if bowl_empty else 'pleine'}")
            # 3. Upload photo + écriture événement dans Firestore
            photo_bytes = camera.capture_bytes()
            photo_path = firebase.upload_photo(photo_bytes, device_id)
            firebase.record_event(device_id, bowl_empty, score, photo_path)
            # 4. Notification push si vide (avec anti-spam)
            if bowl_empty:
                notifier.notify_bowl_empty()
        except Exception as err:
            print(f"Erreur: {err}")  # On ne crash jamais la boucle

    # Première vérif immédiate, puis toutes les X secondes
    check_bowl()
    schedule.every(interval).seconds.do(check_bowl)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()