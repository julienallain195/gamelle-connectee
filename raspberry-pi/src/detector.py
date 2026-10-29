# ============================================
#  DETECTOR.PY = DÉTECTION "GAMELLE VIDE" + CHAT
# ============================================
# Algorithme gamelle : on regarde une zone précise de l'image (la gamelle)
# et on mesure sa "texture". Une gamelle pleine de croquettes = très texturée.
# Une gamelle vide = lisse et uniforme → score bas → "vide".
#
# Détection chat : petit modèle TFLite (SSD MobileNet entraîné sur COCO)
# qui reconnaît la classe "cat". Voir README pour télécharger le modèle.

import cv2
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    # Fallback si tflite-runtime n'est pas installé mais que TensorFlow l'est
    from tensorflow.lite.python.interpreter import Interpreter


class BowlDetector:
    def __init__(self, empty_threshold=35.0):
        # Seuil : en dessous de ce score, la gamelle est considérée comme vide
        self.empty_threshold = empty_threshold
        # Zone de la gamelle dans l'image (x, y, largeur, hauteur en %)
        # À AJUSTER selon le placement de ta caméra !
        self.roi = (0.25, 0.35, 0.5, 0.4)

    def fill_score(self, image_bgr):
        """Calcule un score de remplissage (haut = plein, bas = vide)"""
        rx, ry, rw, rh = self.roi
        h, w = image_bgr.shape[:2]
        # Extraction de la zone de la gamelle
        roi = image_bgr[int(ry*h):int((ry+rh)*h), int(rx*w):int((rx+rw)*w)]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # Écart-type = mesure de texture (croquettes = irrégulier = haut)
        texture = float(np.std(gray))
        # Luminosité moyenne
        brightness = float(np.mean(gray))
        # Score combiné (à calibrer avec tes vraies photos !)
        return round(texture * 0.7 + brightness * 0.3, 2)

    def is_empty(self, image_bgr):
        """Retourne (True si vide, score)"""
        score = self.fill_score(image_bgr)
        return score < self.empty_threshold, score


class CocoDetector:
    """Détecte les chats et les humains via un modèle TFLite SSD MobileNet COCO.
    Sert à la détection du chat ET à l'invalidation des relevés quand la vue
    de la gamelle est masquée par un passage."""

    CAT_CLASS_ID = 16     # classe "cat" dans le jeu COCO
    PERSON_CLASS_ID = 1    # classe "person" dans le jeu COCO

    def __init__(self, model_path, confidence=0.5):
        self.confidence = confidence
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        # Taille d'entrée attendue par le modèle (ex: 300x300)
        self.input_height = int(self.input_details[0]["shape"][1])
        self.input_width = int(self.input_details[0]["shape"][2])

    def detect(self, image_bgr):
        """Retourne [(class_id, score, box), ...] pour les objets détectés.
        box = (ymin, xmin, ymax, xmax) en coordonnées relatives (0.0 → 1.0)."""
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_width, self.input_height))
        input_data = np.expand_dims(resized, axis=0).astype(np.float32)

        self.interpreter.set_tensor(self.input_details[0]["index"], input_data)
        self.interpreter.invoke()

        # Sorties standard d'un modèle SSD : (boîtes, classes, scores, nombre)
        boxes = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
        classes = self.interpreter.get_tensor(self.output_details[1]["index"])[0]
        scores = self.interpreter.get_tensor(self.output_details[2]["index"])[0]

        detections = []
        for box, cls, score in zip(boxes, classes, scores):
            if float(score) >= self.confidence:
                ymin, xmin, ymax, xmax = [float(v) for v in box]
                detections.append((int(cls), float(score), (ymin, xmin, ymax, xmax)))
        return detections

    def seen(self, image_bgr):
        """Retourne (chat_vu: bool, confiance: float)"""
        best = 0.0
        for cls, score, _ in self.detect(image_bgr):
            if cls == self.CAT_CLASS_ID:
                best = max(best, score)
        return best >= self.confidence, round(best, 3)