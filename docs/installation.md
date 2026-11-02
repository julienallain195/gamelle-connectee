# 🚀 Installation complète

Guide pas-à-pas pour mettre la gamelle connectée en production.

## 1. Firebase (déjà fait ✅)

- [x] Projet `gamelle-connectee-2e3be` créé sur console.firebase.google.com
- [x] Firestore (europe-west9) + Storage (bucket us-east1) activés
- [x] Règles déployées (`firebase deploy --only firestore:rules,storage`)
- [x] `mobile-app/.env` rempli avec les vraies clés
- [x] Clé de service téléchargée : `raspberry-pi/service-account.json`

## 2. Préparer la carte microSD (sur le PC)

1. Télécharger **Raspberry Pi Imager** : https://www.raspberrypi.com/software/
2. Choisir l'appareil : *Raspberry Pi 4*
3. OS : **Raspberry Pi OS Lite (64 bits)** (sans bureau, plus léger)
4. Stockage : la microSD (ou une clé USB ≥ 8 Go si pas de lecteur SD — le Pi 4 démarre aussi sur USB)
5. ⚠️ **Avant d'écrire** : cliquer "Personnaliser les réglages" (icône ⚙️ ou bouton "Suivant" propose la config) :
   - Nom d'hôte : `gamelle`
   - **Activer SSH**
   - Nom d'utilisateur + mot de passe (ex : `pi` / un mot de passe solide) — note-les
   - **Wi-Fi** : SSID + mot de passe de ta box (même réseau que ton téléphone)
   - Langue/clavier : fr
6. Écrire, puis insérer la carte dans le Pi (contacts vers le bas côté USB), brancher : le Pi démarre seul

## 3. Première connexion (SSH, depuis le PC)

```bash
# Trouver l'IP du Pi : interface de ta box (192.168.1.x) ou :
ssh tampis@gamelle.local        # souvent plus simple
# mot de passe : celui défini à l'étape 2
```

## 4. Installation du code sur le Pi

```bash
sudo apt update && sudo apt install -y python3-pip python3-venv ffmpeg git
git clone https://github.com/julienallain195/gamelle-connectee.git
cd gamelle-connectee/raspberry-pi

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp config.yaml.example config.yaml
nano config.yaml    # → id du device, éventuellement intervalle
```

Copier les deux fichiers secrets depuis le PC (le plus simple : les recréer) :
- `service-account.json` → le télécharger depuis la console Firebase
  (Paramètres → Comptes de service → Générer une nouvelle clé privée) ou copier celui du PC :
  `scp "C:/Users/<toi>/Documents/projet_app/gamelle-connectee/raspberry-pi/service-account.json" tampis@gamelle.local:gamelle-connectee/raspberry-pi/`

Tester la webcam USB (C270 branchée sur un port USB du Pi) :
```bash
ls /dev/video*   # doit lister au moins /dev/video0
python3 -c "import cv2; c = cv2.VideoCapture(0, cv2.CAP_V4L2); ok, f = c.read(); print('Webcam OK' if ok else 'Webcam KO'); c.release()"
```

Modèle de détection chat (optionnel mais recommandé) :
```bash
mkdir -p models
wget -O models/detect.tflite https://storage.googleapis.com/download.tensorflow.org/models/tflite/task_library/object_detection/android/lite-model_ssd_mobilenet_v1_1_metadata_1.tflite
```

## 5. Test en direct

```bash
python src/main.py
```
Attendre la ligne `🐱 Surveillance démarrée` puis le premier relevé
(`Score: ...`). **Ouvrir l'app mobile** : l'état et la photo réelle doivent
apparaître en temps réel. Ctrl+C pour arrêter.

## 6. Service systemd (démarrage automatique)

```bash
# gamelle.service est déjà configuré pour l'utilisateur "tampis" ;
# si tu changes de nom d'utilisateur, adapte User= et les chemins /home/tampis
sudo cp gamelle.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now gamelle

# Vérifier :
systemctl status gamelle
journalctl -u gamelle -f    # logs en direct (Ctrl+C pour quitter)
```

Après ce point : le Pi survit aux coupures de courant tout seul, et l'app
mobile affiche le statut du service (température, uptime) dans Paramètres.

## 7. Calibrage (à faire avec de vraies photos)

1. Placer la webcam en hauteur, gamelle dégagée dans le champ
2. Regarder les scores affichés pendant quelques cycles :
   gamelle pleine → score haut ; vide → score bas
3. Ajuster le seuil **directement dans l'app** (Paramètres → Seuil "gamelle vide")
4. Ajuster la zone de la gamelle (`detector.py`, attribut `roi` en %)
   si le score ne distingue pas bien les deux états
