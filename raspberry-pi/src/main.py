# ============================================
#  MAIN.PY = CŒUR DU PROGRAMME (boucle principale)
# ============================================
# Ce script tourne en boucle sur le Raspberry :
# 1. Prend une photo (cycle régulier, ou à la demande depuis l'app mobile)
# 2. Analyse si la gamelle est vide + si le chat est visible
# 3. Invalide les relevés si la vue de la gamelle est masquée (chat/humain)
# 4. Enregistre une courte vidéo si le chat est là
# 5. Envoie photo/vidéo + événements à Firebase
# 6. Notifie si la gamelle est vide (après confirmation par 2 relevés)
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
from detector import BowlDetector, CocoDetector
from firebase_client import FirebaseClient
from notifier import PushNotifier

# Nombre d'essais pour obtenir une vue dégagée de la gamelle à chaque relevé
OCCLUSION_RETRIES = 3
OCCLUSION_RETRY_DELAY = 10  # secondes entre les essais

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

def clip_to_mp4(clip_bytes):
    """Convertit un clip MJPEG/.avi (webcam USB) en .mp4 H.264 lisible sur mobile.
    Retourne None si ffmpeg n'est pas installé."""
    if shutil.which("ffmpeg") is None:
        print("⚠️  ffmpeg absent : vidéo ignorée (sudo apt install ffmpeg)")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        avi_path = os.path.join(tmp, "clip.avi")
        mp4_path = os.path.join(tmp, "clip.mp4")
        with open(avi_path, "wb") as f:
            f.write(clip_bytes)
        result = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", avi_path,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", mp4_path]
        )
        if result.returncode != 0:
            return None
        with open(mp4_path, "rb") as f:
            return f.read()

def occlusion_name(detections, roi, min_overlap=0.25):
    """Retourne ('chat'|'personne', score) si un chat ou un humain recouvre
    la zone gamelle, sinon None. Les autres classes (arrière-plan, objets)
    sont ignorées. min_overlap = fraction de la zone gamelle recouverte."""
    rx, ry, rw, rh = roi
    for cls, score, box in detections:
        if cls not in (CocoDetector.CAT_CLASS_ID, CocoDetector.PERSON_CLASS_ID):
            continue
        ymin, xmin, ymax, xmax = box
        # Intersection boîte/zone gamelle (coordonnées relatives 0.0-1.0)
        ix = max(0.0, min(rx + rw, xmax) - max(rx, xmin))
        iy = max(0.0, min(ry + rh, ymax) - max(ry, ymin))
        if ix * iy >= min_overlap * rw * rh:
            return ("chat" if cls == CocoDetector.CAT_CLASS_ID else "personne", round(score, 2))
    return None

def main():
    config = load_config()

    # Initialisation des composants
    camera = Camera(width=config["camera"]["width"], height=config["camera"]["height"])
    detector = BowlDetector(
        empty_threshold=config["camera"]["empty_threshold"],
        roi=tuple(config["camera"].get("roi", (0.25, 0.35, 0.5, 0.4))),
    )
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
    # Nombre de relevés "vide" consécutifs avant d'alerter
    confirm_empty_checks = int(config.get("notifications", {}).get("confirm_empty_checks", 2))
    # Anti-spam chat : délai minimum entre deux photos/vidéos du chat
    cat_cooldown_seconds = int(config.get("detection", {}).get("cat_cooldown_minutes", 10)) * 60
    # Photo comparative "après passage du chat" : délai depuis la détection
    after_cat_delay = int(config.get("detection", {}).get("after_cat_delay_seconds", 180))

    # Détection chat/humain : optionnelle, si le modèle TFLite est présent
    detection_conf = config.get("detection", {})
    coco = None
    model_path = detection_conf.get("cat_model", "models/detect.tflite")
    if model_path and os.path.exists(model_path):
        coco = CocoDetector(
            model_path=model_path,
            confidence=detection_conf.get("cat_confidence", 0.5),
        )
        print("🐱 Détection chat/humain activée")
    else:
        print("⚠️  Modèle TFLite absent (models/detect.tflite) : détection désactivée")

    # Réglages actifs : valeurs de config.yaml, écrasées à distance via l'app
    state = {
        "empty_threshold": float(config["camera"]["empty_threshold"]),
        "check_interval": int(config["camera"]["check_interval_seconds"]),
        "cooldown_minutes": int(config["notifications"]["alert_cooldown_minutes"]),
        "quiet_start": 23,
        "quiet_end": 7,
        "video_on_cat": True,
        "empty_streak": 0,       # relevés "vide" consécutifs (anti-fausse-alerte)
        "last_bowl_empty": None,  # dernier état publié (pour détecter les changements)
        "last_cat_pub_at": 0.0,   # heure du dernier passage de chat publié
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

    def capture_after_passage(event_id):
        """Photo + score APRÈS le passage du chat : comparaison avant/après
        pour voir s'il a mangé. Programmée par Timer après la détection."""
        with capture_lock:
            try:
                image = camera.capture_array()
                bowl_empty, score = detector.is_empty(image)
                photo_path = firebase.upload_photo(camera.capture_bytes(), device_id)
                firebase.update_event_after(event_id, photo_path, score, bowl_empty)
                print(f"📸 Photo 'après passage' publiée (score: {score})")
            except Exception as err:
                print(f"Erreur photo après passage: {err}")

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
                    # 1. Photo, avec nouveaux essais si la vue est masquée
                    image = None
                    occluded_by = None
                    for attempt in range(OCCLUSION_RETRIES):
                        image = camera.capture_array()
                        if not coco:
                            break  # pas de détecteur : on ne peut pas vérifier la vue
                        occluded_by = occlusion_name(coco.detect(image), detector.roi)
                        if not occluded_by:
                            break
                        print(f"🚧 Vue masquée par {occluded_by[0]} ({occluded_by[1]}) — nouvel essai {attempt + 1}/{OCCLUSION_RETRIES}")
                        time.sleep(OCCLUSION_RETRY_DELAY)

                    if occluded_by:
                        if on_demand:
                            # À la demande, la photo est utile même masquée :
                            # on la publie mais sans mesurer l'état de la gamelle.
                            print("🚧 Vue toujours masquée : photo publiée, état non mesuré")
                            photo_path = firebase.upload_photo(camera.capture_bytes(), device_id)
                            firebase.record_event(device_id, None, None, photo_path,
                                                  occluded=True, on_demand=True)
                        else:
                            # Relevé planifié masqué : aucune donnée enregistrée
                            print("🚧 Vue masquée : relevé ignoré")
                        return

                    # 2. Analyser : gamelle vide ? chat visible ?
                    bowl_empty, score = detector.is_empty(image)
                    cat_seen, cat_confidence = (False, 0.0)
                    if coco:
                        cat_seen, cat_confidence = coco.seen(image)
                    print(f"Score: {score} → {'VIDE' if bowl_empty else 'pleine'}"
                          f" | chat: {'oui' if cat_seen else 'non'} ({cat_confidence})")
                    # 3. Publier une photo/vidéo SEULEMENT si c'est utile :
                    #    - premier relevé ou changement d'état de la gamelle
                    #    - passage du chat (avec anti-spam : 1 publication max
                    #      toutes les X minutes même s'il reste devant)
                    #    - demande explicite depuis l'app
                    # Sinon (gamelle inchangée, pas de chat) : rien n'est envoyé.
                    first_reading = state["last_bowl_empty"] is None
                    state_changed = (not first_reading) and (bowl_empty != state["last_bowl_empty"])
                    cat_to_publish = cat_seen and (time.monotonic() - state["last_cat_pub_at"]) >= cat_cooldown_seconds
                    if on_demand or first_reading or state_changed or cat_to_publish:
                        video_path = None
                        if cat_seen and state["video_on_cat"]:
                            clip = clip_to_mp4(camera.record_clip(clip_seconds))
                            if clip:
                                video_path = firebase.upload_video(clip, device_id)
                        photo_path = firebase.upload_photo(camera.capture_bytes(), device_id)
                        event_id = firebase.record_event(device_id, bowl_empty, score, photo_path,
                                              cat_seen=cat_seen, on_demand=on_demand,
                                              video_path=video_path)
                        if cat_seen:
                            firebase.record_sighting(device_id, cat_confidence)
                            state["last_cat_pub_at"] = time.monotonic()
                            # Comparaison avant/après : photo retardée attachée à l'événement
                            threading.Timer(
                                after_cat_delay, capture_after_passage, args=(event_id,)
                            ).start()
                        reason = ("premier relevé" if first_reading
                                  else "changement d'état" if state_changed
                                  else "chat vu" if cat_seen else "demande de l'app")
                        print(f"📤 Publié ({reason})")
                    state["last_bowl_empty"] = bowl_empty
                    # 4. Compteurs du jour + notification si vide confirmé
                    firebase.update_daily_stats(bowl_empty, cat_seen)
                    if bowl_empty:
                        state["empty_streak"] += 1
                        if state["empty_streak"] >= confirm_empty_checks:
                            notifier.notify_bowl_empty()
                    else:
                        state["empty_streak"] = 0
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
