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
    def __init__(self, width=1280, height=720, device_index=0, fps=15):
        """Ouvre la webcam USB à la résolution donnée"""
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
        # Laisse le capteur se stabiliser (exposition automatique)
        time.sleep(2)
        warmup = self.capture_array()
        self.frame_size = (warmup.shape[1], warmup.shape[0])  # (largeur, hauteur)

    def capture_array(self):
        """Capture une image → retourne un tableau numpy BGR (pour l'analyse)"""
        ok, frame = self.cap.read()
        if not ok or frame is None:
            raise RuntimeError("Échec de lecture de la webcam")
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
