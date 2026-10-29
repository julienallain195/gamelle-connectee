# ============================================
#  NOTIFIER.PY = ENVOI DES NOTIFICATIONS PUSH
# ============================================
# Utilise l'API Expo Push (gratuite) pour envoyer des alertes
# sur le téléphone de l'utilisateur.

import time
import requests

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

class PushNotifier:
    def __init__(self, expo_push_token, cooldown_minutes=30):
        self.token = expo_push_token
        # Anti-spam : attendre X minutes entre 2 alertes
        self.cooldown_seconds = cooldown_minutes * 60
        self._last_alert_at = 0.0

    def update_cooldown(self, cooldown_minutes):
        """Modifie l'anti-spam (réglage à distance depuis l'app)"""
        self.cooldown_seconds = cooldown_minutes * 60

    def _can_send(self):
        """Vérifie si le cooldown est passé"""
        return (time.time() - self._last_alert_at) >= self.cooldown_seconds

    def send(self, title, body, data=None):
        """Envoie une notification push via l'API Expo"""
        if not self.token or not self._can_send():
            return False
        payload = {"to": self.token, "title": title, "body": body, "sound": "default", "data": data or {}}
        try:
            response = requests.post(EXPO_PUSH_URL, json=payload, timeout=10)
            if response.status_code == 200:
                self._last_alert_at = time.time()
                return True
        except requests.RequestException as err:
            print(f"Erreur notification: {err}")
        return False

    def notify_bowl_empty(self):
        """Alerte spéciale : gamelle vide !"""
        return self.send("🚨 Gamelle vide !", "Ton chat n'a plus de croquettes 🐱", {"type": "bowl_empty"})