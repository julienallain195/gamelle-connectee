# 🐍 Code Raspberry Pi

Programme Python qui surveille la gamelle du chat.

## Installation sur le Pi

```bash
# 1. Dépendances système (conversion vidéo pour les clips)
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg

# 2. Environnement virtuel
cd raspberry-pi
python3 -m venv venv
source venv/bin/activate

# 3. Librairies Python
pip install -r requirements.txt

# 4. Configuration
cp config.yaml.example config.yaml
# → édite config.yaml avec tes vraies valeurs
# → place service-account.json (clé Firebase) dans ce dossier

# 5. Test webcam USB (branchée, ex: Logitech C270)
ls /dev/video*   # doit afficher /dev/video0 (ou plus)
python3 -c "import cv2; c = cv2.VideoCapture(0, cv2.CAP_V4L2); ok, frame = c.read(); print('Webcam OK' if ok else 'Webcam KO'); c.release()"

# 6. Détection de chat (optionnelle mais recommandée)
mkdir -p models
# Modèle SSD MobileNet COCO (reconnaît la classe "cat", ~4 Mo) :
wget -O models/detect.tflite https://storage.googleapis.com/download.tensorflow.org/models/tflite/task_library/object_detection/android/lite-model_ssd_mobilenet_v1_1_metadata_1.tflite
# (si le lien ne marche plus : chercher "ssd mobilenet coco tflite" sur tfhub.dev)

# 7. Lancement
python src/main.py

## Fonctionnement

- Toutes les 60s (paramétrable) : photo → analyse gamelle + chat → Firebase.
- À la demande : l'app mobile écrit un document dans la collection `commands`
  (`type: capture`, `status: pending`) ; le Pi l'écoute, prend une photo
  immédiatement et marque la commande `done`.
- Si le chat est détecté : courte vidéo MJPEG réencodée en mp4 (ffmpeg requis),
  envoyée dans `videos/`, plus un document dans `catSightings`.
- Réglages à distance : l'app écrit dans `settings/gamelle`
  (seuil "vide", intervalle, anti-spam, heures silencieuses, vidéo on/off) ;
  le Pi applique les changements en temps réel.
- État du Pi (température, uptime, dernier relevé) publié dans `status/<device>`.
- Stats du jour (relevés pleines/vides, passages du chat) dans `dailyStats/<date>`.

Note : le code est écrit pour une **webcam USB** (OpenCV/V4L2, ex: Logitech C270).
Pour un module caméra CSI officiel, il faudrait repasser à picamera2.