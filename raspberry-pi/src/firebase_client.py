# ============================================
#  FIREBASE_CLIENT.PY = ENVOI DES DONNÉES À FIREBASE
# ============================================
# Upload les photos sur Firebase Storage
# et écrit les événements dans Firestore (base de données).

import uuid
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, storage

class FirebaseClient:
    def __init__(self, credentials_file, project_id, storage_bucket):
        """Connexion à Firebase avec la clé de service"""
        cred = credentials.Certificate(credentials_file)
        firebase_admin.initialize_app(cred, {
            "projectId": project_id,
            "storageBucket": storage_bucket,
        })
        self.db = firestore.client()
        self.bucket = storage.bucket()

    def upload_photo(self, image_bytes, device_id):
        """Upload une photo → retourne son chemin dans Storage"""
        filename = f"photos/{device_id}/{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
        blob = self.bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        return filename

    def record_event(self, device_id, bowl_empty, score, photo_path):
        """Écrit un événement dans la collection 'events' de Firestore"""
        self.db.collection("events").add({
            "deviceId": device_id,
            "bowlEmpty": bowl_empty,
            "fillScore": score,
            "photoPath": photo_path,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })