# ============================================
#  FIREBASE_CLIENT.PY = ENVOI DES DONNÉES À FIREBASE
# ============================================
# Upload les photos/vidéos sur Firebase Storage
# et écrit les événements, stats et réglages dans Firestore.

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

    def upload_video(self, video_bytes, device_id):
        """Upload un clip vidéo (mp4) → retourne son chemin dans Storage"""
        filename = f"videos/{device_id}/{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.mp4"
        blob = self.bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")
        return filename

    def record_event(self, device_id, bowl_empty, score, photo_path,
                     cat_seen=False, on_demand=False, video_path=None, occluded=False):
        """Écrit un événement dans la collection 'events' de Firestore.
        bowl_empty/score peuvent être None si la vue était masquée.
        Retourne l'id du document (pour le compléter ensuite, ex: avant/après)."""
        doc_ref = self.db.collection("events").document()
        doc_ref.set({
            "deviceId": device_id,
            "bowlEmpty": bowl_empty,
            "fillScore": score,
            "photoPath": photo_path,
            "videoPath": video_path,
            "catSeen": cat_seen,
            "onDemand": on_demand,
            "occluded": occluded,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })
        return doc_ref.id

    def update_event_after(self, event_id, photo_path, score, bowl_empty):
        """Attache la photo et le score 'APRÈS passage du chat' à un événement."""
        self.db.collection("events").document(event_id).set({
            "afterPhotoPath": photo_path,
            "afterFillScore": score,
            "afterBowlEmpty": bowl_empty,
            "afterAt": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    def record_sighting(self, device_id, confidence):
        """Écrit un passage du chat dans 'catSightings' (pour l'onglet Chat)"""
        self.db.collection("catSightings").add({
            "deviceId": device_id,
            "confidence": confidence,
            "timestamp": firestore.SERVER_TIMESTAMP,
        })

    def update_daily_stats(self, bowl_empty, cat_seen):
        """Incrémente les compteurs du jour dans 'dailyStats/<YYYY-MM-DD>'"""
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.db.collection("dailyStats").document(date_str).set({
            "date": date_str,
            "fullChecks": firestore.Increment(0 if bowl_empty else 1),
            "emptyChecks": firestore.Increment(1 if bowl_empty else 0),
            "catSightings": firestore.Increment(1 if cat_seen else 0),
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    def write_status(self, device_id, data):
        """Publie l'état du Raspberry dans 'status/<deviceId>' (onglet Paramètres)"""
        self.db.collection("status").document(device_id).set(
            {**data, "lastSeen": firestore.SERVER_TIMESTAMP}, merge=True
        )

    def watch_commands(self, device_id, on_command):
        """Écoute les commandes 'pending' adressées à ce Raspberry.
        on_command(command_id, data) est appelé pour chaque commande reçue.
        Retourne un objet watch à conserver (sinon l'écoute s'arrête)."""
        q = (
            self.db.collection("commands")
            .where(filter=firestore.FieldFilter("deviceId", "==", device_id))
            .where(filter=firestore.FieldFilter("status", "==", "pending"))
        )
        def _on_snapshot(snap, changes, read_time):
            # Signature imposée par google-cloud-firestore : 3 arguments
            for doc in snap:
                data = doc.to_dict()
                if data.get("status") == "pending":
                    on_command(doc.id, data)
        return q.on_snapshot(_on_snapshot)

    def mark_command_done(self, command_id, skipped=False):
        """Marque une commande comme traitée (l'app mobile attend ce statut)"""
        self.db.collection("commands").document(command_id).set({
            "status": "done",
            "skippedQuiet": skipped,
            "doneAt": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    def watch_settings(self, on_settings):
        """Écoute le document settings/gamelle : réglages modifiables depuis l'app.
        on_settings(data) est appelé à chaque changement."""
        def _on_snapshot(doc_snapshot, changes, read_time):
            # Signature imposée par google-cloud-firestore : 3 arguments
            on_settings(doc_snapshot[0].to_dict() if doc_snapshot else None)
        return self.db.collection("settings").document("gamelle").on_snapshot(_on_snapshot)
