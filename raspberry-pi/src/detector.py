# ============================================
#  DETECTOR.PY = DÉTECTION "GAMELLE VIDE"
# ============================================
# Algorithme simple : on regarde une zone précise de l'image (la gamelle)
# et on mesure sa "texture". Une gamelle pleine de croquettes = très texturée.
# Une gamelle vide = lisse et uniforme → score bas → "vide".

import cv2
import numpy as np

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