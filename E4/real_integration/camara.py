import os
import cv2


def abrir_camara(indice):
    cap = cv2.VideoCapture(indice, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(indice)
    if not cap.isOpened() and os.name == "nt":
        cap.release()
        cap = cv2.VideoCapture(indice)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"No se pudo abrir la cámara {indice}. Prueba --camera 1")
    return cap

