# ============================================
#  CLEANUP_SIMULATED.PY = NETTOYER LES DONNÉES DE TEST
# ============================================
# Supprime les données créées pendant les tests sans Raspberry :
#  1. Les événements "simulate_*" (envoyés par simulate.py) + leurs photos
#  2. Tous les passages de chat (catSightings)
#  3. Les stats journalières (dailyStats) — recomptées par le Pi ensuite
# Les vrais relevés/vidéos du Raspberry sont conservés.
#
# Utilisation (sur le Pi, depuis raspberry-pi/ avec le venv actif) :
#   python cleanup_simulated.py

import firebase_admin
from firebase_admin import credentials, firestore, storage

cred = credentials.Certificate("service-account.json")
firebase_admin.initialize_app(cred, {
    "projectId": "gamelle-connectee-2e3be",
    "storageBucket": "gamelle-connectee-2e3be.firebasestorage.app",
})
db = firestore.client()
bucket = storage.bucket()

# 1. Événements simulés + leurs photos
batch = db.batch()
deleted_events = 0
for doc in db.collection("events").get():
    photo_path = doc.to_dict().get("photoPath") or ""
    if "simulate_" in photo_path:
        try:
            bucket.blob(photo_path).delete()
        except Exception:
            pass  # photo déjà absente : on continue
        batch.delete(doc.reference)
        deleted_events += 1
batch.commit()
print(f"✅ {deleted_events} événements simulés supprimés (avec leurs photos)")

# 2. Tous les passages de chat (les tests en contiennent, le Pi recommence)
batch = db.batch()
deleted_sightings = 0
for doc in db.collection("catSightings").get():
    batch.delete(doc.reference)
    deleted_sightings += 1
batch.commit()
print(f"✅ {deleted_sightings} passages supprimés")

# 3. Stats journalières (les compteurs des tests sont inclus dedans)
deleted_stats = 0
for doc in db.collection("dailyStats").get():
    doc.reference.delete()
    deleted_stats += 1
print(f"✅ {deleted_stats} jours de stats réinitialisés (le Pi les recrée)")

print("\nDonnées de test supprimées. L'app se met à jour toute seule.")
