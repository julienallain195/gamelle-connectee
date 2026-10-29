# 🐍 Code Raspberry Pi

Programme Python qui surveille la gamelle du chat.

## Installation sur le Pi

```bash
# 1. Dépendances système (caméra)
sudo apt update && sudo apt install -y python3-pip python3-venv libcamera-apps

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

# 6. Lancement
python src/main.py