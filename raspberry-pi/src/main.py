# ============================================
#  MAIN.PY = CŒUR DU PROGRAMME (boucle principale)
# ============================================
# Ce script tourne en boucle sur le Raspberry :
# 1. Prend une photo (cycle régulier, ou à la demande depuis l'app mobile)
# 2. Analyse si la gamelle est vide + si le chat est visible
# 3. Enregistre une courte vidéo si le chat est là
# 4. Envoie photo/vidéo + événements à Firebase
# 5. Notifie si la gamelle est vide
#
# Les réglages (seuil, intervalle, heures silencieuses, vidéo) peuvent être
# modifiés à distance depuis l'app mobile (document Firestore settings/gamelle).

import datetime
import os
import shutil
import subprocess
import tempfile
import threading
import time
import yaml

from camera import Camera
from detector import BowlDetector, CatDetector
from firebase_client import FirebaseClient
from notifier import PushNotifier

def load_config(path="config.yaml"):
    """Lit le fichier de configuration config.yaml"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)

def read_cpu_temp():
    """Température du CPU (°C), None si non disponible"""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return float(f.read().strip()) / 1000.0
    except OSError:
        return None

def read_uptime():
    """Durée depuis le démarrage du Pi (secondes), None si non disponible"""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except OSError:
        return None

def h264_to_mp4(h264_bytes):
    """Convertit un flux H.264 brut en .mp4 avec ffmpeg (lecture mobile).
    Retourne None si ffmpeg n'est pas installé."""
    if shutil.which("ffmpeg") is None:
        print("⚠️  ffmpeg absent : vidéo ignorée (sudo apt install ffmpeg)")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "clip.h264")
        mp4_path = os.path.join(tmp, "clip.mp4")
        with open(raw_path, "wb") as f:
            f.write(h264_bytes)
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", raw_path, "-c", "copy", mp4_path]
        )
        if result.returncode != 0:
            return None
        with open(mp4_path, "rb") as f:
            return f.read()

def main():
    config = load_config()

    # Initialisation des composants
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
    clip_seconds = config.get("video", {}).get("clip_seconds", 6)

    # Détection de chat : optionnelle, si le modèle TFLite est présent
    detection_conf = config.get("detection", {})
    cat_detector = None
    model_path = detection_conf.get("cat_model", "models/detect.tflite")
    if model_path and os.path.exists(model_path):
        cat_detector = CatDetector(
            model_path=model_path,
            confidence=detection_conf.get("cat_confidence", 0.5),
        )
        print("🐱 Détection de chat activée")
    else:
        print("⚠️  Modèle TFLite absent (models/detect.tflite) : détection de chat désactivée")

    # Réglages actifs : valeurs de config.yaml, écrasées à distance via l'app
    state = {
        "empty_threshold": float(config["camera"]["empty_threshold"]),
        "check_interval": int(config["camera"]["check_interval_seconds"]),
        "cooldown_minutes": int(config["notifications"]["alert_cooldown_minutes"]),
        "quiet_start": 23,
        "quiet_end": 7,
        "video_on_cat": True,
    }

    def apply_remote_settings(data):
        """Réglages modifiés depuis l'app mobile (settings/gamelle)"""
        if not data:
            return
        if data.get("emptyThreshold") is not None:
            state["empty_threshold"] = float(data["emptyThreshold"])
            detector.empty_threshold = state["empty_threshold"]
        if data.get("checkIntervalSeconds"):
            state["check_interval"] = max(10, int(data["checkIntervalSeconds"]))
        if data.get("alertCooldownMinutes") is not None:
            state["cooldown_minutes"] = int(data["alertCooldownMinutes"])
            notifier.update_cooldown(state["cooldown_minutes"])
        if data.get("quietStartHour") is not None:
            state["quiet_start"] = int(data["quietStartHour"])
        if data.get("quietEndHour") is not None:
            state["quiet_end"] = int(data["quietEndHour"])
        if data.get("videoOnCat") is not None:
            state["video_on_cat"] = bool(data["videoOnCat"])
        print(f"⚙️  Réglages actifs: {state}")

    firebase.watch_settings(apply_remote_settings)

    def in_quiet_hours(now):
        """Vrai pendant les heures silencieuses (ex: 23h → 7h)"""
        hour = now.hour
        start, end = state["quiet_start"], state["quiet_end"]
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end  # plage qui passe minuit

    # La caméra ne supporte pas 2 captures simultanées :
    # le verrou sépare les relevés planifiés des captures à la demande.
    capture_lock = threading.Lock()

    def check_bowl(on_demand=False, command_id=None):
        """Une vérification complète : photo → détection → Firebase → notif"""
        with capture_lock:
            skipped_quiet = False
            score = None
            bowl_empty = None
            try:
                now = datetime.datetime.now()
                if in_quiet_hours(now):
                    # Heures silencieuses : pas de capture (pas de flash/bruit la nuit)
                    skipped_quiet = True
                    print("🌙 Heures silencieuses : capture ignorée")
                else:
                    # 1. Prendre une photo
                    image = camera.capture_array()
                    # 2. Analyser : gamelle vide ? chat visible ?
                    bowl_empty, score = detector.is_empty(image)
                    cat_seen, cat_confidence = (False, 0.0)
                    if cat_detector:
                        cat_seen, cat_confidence = cat_detector.seen(image)
                    print(f"Score: {score} → {'VIDE' if bowl_empty else 'pleine'}"
                          f" | chat: {'oui' if cat_seen else 'non'} ({cat_confidence})")
                    # 3. Vidéo courte si le chat est là (optionnel)
                    video_path = None
                    if cat_seen and state["video_on_cat"]:
                        clip = h264_to_mp4(camera.record_clip(clip_seconds))
                        if clip:
                            video_path = firebase.upload_video(clip, device_id)
                    # 4. Upload photo + événement + passage + stats du jour
                    photo_path = firebase.upload_photo(camera.capture_bytes(), device_id)
                    firebase.record_event(device_id, bowl_empty, score, photo_path,
                                          cat_seen=cat_seen, on_demand=on_demand,
                                          video_path=video_path)
                    if cat_seen:
                        firebase.record_sighting(device_id, cat_confidence)
                    firebase.update_daily_stats(bowl_empty, cat_seen)
                    # 5. Notification push si vide (avec anti-spam)
                    if bowl_empty:
                        notifier.notify_bowl_empty()
            except Exception as err:
                print(f"Erreur: {err}")  # On ne crash jamais la boucle
            finally:
                try:
                    # État du Pi visible dans l'onglet Paramètres
                    firebase.write_status(device_id, {
                        "cpuTemp": read_cpu_temp(),
                        "uptimeSeconds": read_uptime(),
                        "lastScore": score,
                        "bowlEmpty": bowl_empty,
                    })
                except Exception as err:
                    print(f"Erreur statut: {err}")
                # On marque la commande comme traitée même en cas d'erreur,
                # pour que l'app mobile ne reste pas bloquée sur "en cours".
                if command_id:
                    firebase.mark_command_done(command_id, skipped=skipped_quiet)

    def on_command(command_id, data):
        """Capture à la demande, déclenchée depuis l'app mobile"""
        if data.get("type") == "capture":
            print("📸 Capture à la demande reçue depuis l'app")
            check_bowl(on_demand=True, command_id=command_id)

    # L'app mobile peut demander une photo instantanée via la collection 'commands'
    firebase.watch_commands(device_id, on_command)

    print(f"🐱 Surveillance démarrée (toutes les {state['check_interval']}s)")

    # Première vérif immédiate, puis à intervalle régulier
    # (l'intervalle peut changer à distance : on relit state à chaque tour)
    check_bowl()
    next_check = time.monotonic() + state["check_interval"]
    while True:
        if time.monotonic() >= next_check:
            check_bowl()
            next_check = time.monotonic() + state["check_interval"]
        time.sleep(1)

if __name__ == "__main__":
    main()
