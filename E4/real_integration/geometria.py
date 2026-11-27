import math
import numpy as np


def estado_robot(blobs, colores, offset_frente: float = 0.0):

    detectados = {c.nombre: b for c, b in zip(colores, blobs)}
    f, r, b = (detectados.get(n) for n in ("DELANTE", "ATRAS", "BALON"))
    if f is None or r is None or b is None:
        return None
    delantero = np.array(f.centro, dtype=float)
    trasero = np.array(r.centro, dtype=float)
    balon = np.array(b.centro, dtype=float)
    vector_robot = delantero - trasero
    vector_objetivo = balon - delantero
    norma_robot = np.linalg.norm(vector_robot)
    norma_objetivo = np.linalg.norm(vector_objetivo)
    if norma_robot < 1 or norma_objetivo < 1:
        return None
    cruz = float(np.linalg.det(np.stack((vector_robot, vector_objetivo))))
    punto = float(np.dot(vector_robot, vector_objetivo))
    angulo = math.degrees(math.atan2(cruz, punto))
    _, _, ancho, alto = b.recuadro
    radio_balon = max(ancho, alto) / 2.0
    distancia_libre = max(0.0, float(norma_objetivo) - radio_balon - offset_frente)
    return distancia_libre, angulo

