# 🚀 Installation complète

## 1. Firebase
- Créer un projet sur console.firebase.google.com
- Activer Firestore, Storage, Cloud Messaging
- Télécharger la clé de service (Paramètres > Comptes de service)

## 2. Raspberry Pi
```bash
cd raspberry-pi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config.yaml.example config.yaml  # puis éditer
python src/main.py