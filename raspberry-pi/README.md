# 🐍 Code Raspberry Pi

Programme Python qui surveille la gamelle du chat.

## Installation sur le Pi

```bash
# 1. Dépendances système (caméra + conversion vidéo)
sudo apt update && sudo apt install -y python3-pip python3-venv libcamera-apps ffmpeg

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

# 5. Test caméra
libcamera-jpeg -o test.jpg

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
- Si le chat est détecté : courte vidéo H.264 convertie en mp4 (ffmpeg requis),
  envoyée dans `videos/`, plus un document dans `catSightings`.
- Réglages à distance : l'app écrit dans `settings/gamelle`
  (seuil "vide", intervalle, anti-spam, heures silencieuses, vidéo on/off) ;
  le Pi applique les changements en temps réel.
- État du Pi (température, uptime, dernier relevé) publié dans `status/<device>`.
- Stats du jour (relevés pleines/vides, passages du chat) dans `dailyStats/<date>`.