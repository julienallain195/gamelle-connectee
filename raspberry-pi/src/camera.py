# ============================================
#  CAMERA.PY = GESTION DE LA CAMÉA (WEBCAM USB via OpenCV)
# ============================================
# Compatible avec les webcams USB (ex: Logitech C270) via le pilote V4L2.
# Note : picamera2 ne fonctionne qu'avec les modules caméra CSI du Raspberry ;
# pour une webcam USB, on passe par OpenCV.

import os
import tempfile
import time

import cv2

class Camera:
    def __init__(self, width=1280, height=720, device_index=0, fps=15,
                 settings=None, night_boost=False):
        """Ouvre la webcam USB à la résolution donnée.
        settings : réglages webcam (brightness, gain, contrast...) appliqués
                   via V4L2 ; les valeurs non supportées sont ignorées.
        night_boost : éclaircissement logiciel (CLAHE) des images sombres."""
        self.night_boost = night_boost
        self.cap = cv2.VideoCapture(device_index, cv2.CAP_V4L2)
        # Flux MJPEG : indispensable pour obtenir du 720p fluide en USB
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Webcam introuvable (index {device_index}). Branchée ? Voir 'ls /dev/video*'"
            )
        for key, value in (settings or {}).items():
            prop = getattr(cv2, f"CAP_PROP_{key.upper()}", None)
            if prop is None or not self.cap.set(prop, value):
                print(f"⚠️  Réglage webcam {key}={value} refusé ou inconnu")
        # Laisse le capteur se stabiliser (exposition automatique)
        time.sleep(2)
        warmup = self.capture_array()
        self.frame_size = (warmup.shape[1], warmup.shape[0])  # (largeur, hauteur)

    def _boost(self, frame):
        """Éclaircit une image sombre (CLAHE : contraste adaptatif sur la luminance)"""
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        luminance, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        luminance = clahe.apply(luminance)
        return cv2.cvtColor(cv2.merge((luminance, a, b)), cv2.COLOR_LAB2BGR)

    def capture_array(self):
        """Capture une image → retourne un tableau numpy BGR (pour l'analyse)"""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError("Échec de lecture de la webcam")
        if self.night_boost:
            frame = self._boost(frame)
        return frame

    def capture_bytes(self):
        """Capture une image → retourne des octets JPEG (pour l'upload)"""
        ok, buf = cv2.imencode(".jpg", self.capture_array(),
                               [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError("Échec d'encodage JPEG")
        return buf.tobytes()

    def record_clip(self, seconds=6, fps=15):
        """Enregistre un clip MJPEG (.avi) → retourne les octets du fichier"""
        fd, avi_path = tempfile.mkstemp(suffix=".avi")
        os.close(fd)
        writer = cv2.VideoWriter(
            avi_path, cv2.VideoWriter_fourcc(*"MJPG"), fps, self.frame_size
        )
        try:
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                ok, frame = self.cap.read()
                if ok:
                    writer.write(frame)
        finally:
            writer.release()
        with open(avi_path, "rb") as f:
            data = f.read()
        os.unlink(avi_path)
        return data

    def close(self):
        self.cap.release()
