# ============================================
#  CAMERA.PY = GESTION DE LA CAMÉRA
# ============================================
# Utilise picamera2 (librairie officielle Raspberry Pi)
# pour prendre des photos avec la caméra.

import io
import time
import numpy as np
from picamera2 import Picamera2

class Camera:
    def __init__(self, width=1280, height=720):
        """Démarre la caméra avec la résolution donnée"""
        self.picam = Picamera2()
        config = self.picam.create_still_configuration(main={"size": (width, height)})
        self.picam.configure(config)
        self.picam.start()
        time.sleep(2)  # Laisse le capteur se stabiliser

    def capture_array(self):
        """Capture une image → retourne un tableau numpy (pour l'analyse OpenCV)"""
        return self.picam.capture_array()

    def capture_bytes(self):
        """Capture une image → retourne des octets JPEG (pour l'upload)"""
        stream = io.BytesIO()
        self.picam.capture_file(stream, format="jpeg")
        return stream.getvalue()

    def close(self):
        self.picam.close()