# Funciones de percepcion que usa el controlador del simulador
# Detectan los dos circulos del robot y la pelota con mascaras HSV
# y calculan la distancia y el angulo del robot respecto a la pelota
import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# Area minima en pixeles para aceptar una deteccion y no confundirla con ruido
AREA_MINIMA_PX = 80
# Tamano del kernel usado para limpiar las mascaras
TAM_KERNEL = 3
KERNEL = np.ones((TAM_KERNEL, TAM_KERNEL), dtype=np.uint8)

# Cada color tiene un nombre, el color BGR con que se dibuja y sus rangos de H, S y V
# El circulo azul es el delantero, el rojo es el trasero y la pelota es amarilla
# En H (tono), si el minimo supera el maximo, el intervalo cruza por H=0.
RANGOS_INICIALES = [
    ("DELANTE", (255, 0, 0), {"H": [112, 126], "S": [206, 255], "V": [202, 255]}),
    ("ATRAS", (0, 0, 255), {"H": [170, 10], "S": [85, 255], "V": [60, 255]}),
    ("BALON", (0, 255, 255), {"H": [20, 40], "S": [85, 255], "V": [90, 255]}),
]


# Guarda la configuracion de un color y permite volver a sus rangos iniciales
@dataclass
class ColorConfig:
    nombre: str
    color_bgr: Tuple[int, int, int]
    valores_iniciales: Dict[str, List[int]]
    rangos: Dict[str, List[int]] = field(init=False)
    ultimo_click: Optional[Tuple[int, int]] = None
    previo_al_click: Optional[Dict[str, List[int]]] = None

    def __post_init__(self):
        self.reiniciar()

    def reiniciar(self):
        self.rangos = copy.deepcopy(self.valores_iniciales)
        self.ultimo_click = None
        self.previo_al_click = None


# Guarda una deteccion con su bounding box, su centro y su area
@dataclass
class Blob:
    recuadro: Tuple[int, int, int, int]  # x, y, ancho, alto
    centro: Tuple[float, float]
    area: int

# Crea la mascara binaria de un color a partir de la imagen en HSV
def crear_mascara(hsv: np.ndarray, rangos: Dict[str, List[int]]) -> np.ndarray:
    h0, h1 = rangos["H"]
    s0, s1 = rangos["S"]
    v0, v1 = rangos["V"]

    # Si el rango de tono es normal se usa una sola mascara
    if h0 <= h1:
        mascara = cv2.inRange(hsv, (h0, s0, v0), (h1, s1, v1))
    # Si el rango pasa por el cero, como en el rojo, se juntan dos mascaras
    else:
        superior = cv2.inRange(hsv, (h0, s0, v0), (179, s1, v1))
        inferior = cv2.inRange(hsv, (0, s0, v0), (h1, s1, v1))
        mascara = cv2.bitwise_or(superior, inferior)

    # La apertura elimina puntos sueltos y el cierre rellena huecos pequeños
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, KERNEL)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, KERNEL)
    return mascara


# Busca la mancha mas grande de la mascara y entrega su bounding box y su centro
def buscar_blob_principal(mascara: np.ndarray) -> Optional[Blob]:
    cantidad, _, estadisticas, centroides = cv2.connectedComponentsWithStats(
        mascara, connectivity=8
    )
    # Si solo esta el fondo no hay nada detectado
    if cantidad <= 1:
        return None

    # 0 corresponde al fondo, no considerar.
    areas = estadisticas[1:, cv2.CC_STAT_AREA]
    indice = 1 + int(np.argmax(areas))
    area = int(estadisticas[indice, cv2.CC_STAT_AREA])
    # Si la mancha es muy pequeña se considera ruido
    if area < AREA_MINIMA_PX:
        return None

    x = int(estadisticas[indice, cv2.CC_STAT_LEFT])
    y = int(estadisticas[indice, cv2.CC_STAT_TOP])
    ancho = int(estadisticas[indice, cv2.CC_STAT_WIDTH])
    alto = int(estadisticas[indice, cv2.CC_STAT_HEIGHT])
    cx, cy = centroides[indice]
    return Blob((x, y, ancho, alto), (float(cx), float(cy)), area)


# Pasa la imagen a HSV y obtiene la mascara y la deteccion de cada color
def procesar_imagen(imagen: np.ndarray, colores: List[ColorConfig]):
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    mascaras = []
    blobs = []

    for color in colores:
        mascara = crear_mascara(hsv, color.rangos)
        mascaras.append(mascara)
        blobs.append(buscar_blob_principal(mascara))

    return mascaras, blobs


# Calcula la distancia en pixeles y el angulo en grados entre el robot y la pelota
# El angulo es 0 cuando la pelota esta justo al frente y va de menos 180 a 180
def calcular_geometria(blobs: List[Optional[Blob]]) -> Optional[Tuple[float, float]]:
    # Distancia en px, angulo en grados
    delantero, trasero, balon = blobs  # Mismo orden que en la lista de rangos
    if delantero is None or trasero is None or balon is None:
        return None

    # Centros del circulo trasero, del delantero y de la pelota
    pr = np.array(trasero.centro, dtype=float)
    pf = np.array(delantero.centro, dtype=float)
    pb = np.array(balon.centro, dtype=float)
    h = pf - pr  # Orientacion del robot desde el circulo trasero al delantero
    t = pb - pr  # Vector desde el circulo trasero hasta la pelota

    distancia = float(np.linalg.norm(t))
    if np.linalg.norm(h) < 1e-6 or distancia < 1e-6:
        return None  # No hay una direccion bien definida

    # Con el producto cruz y el producto punto se obtiene el angulo con signo
    producto_cruz = h[0] * t[1] - h[1] * t[0]
    producto_punto = np.dot(h, t)
    angulo = float(np.degrees(np.arctan2(producto_cruz, producto_punto)))
    return distancia, angulo


# Guarda los colores configurados y el estado de la vista
class InterfazPercepcion:
    def __init__(self):
        self.colores = [ColorConfig(*datos) for datos in RANGOS_INICIALES]
        self.activo = 0
        # Vista 0 es la camara, 1 la mascara activa y 2 la union de las tres mascaras
        self.vista = 0
        self.imagen_actual = None
        self.area_imagen_real = (0, 0, 0, 0)
        self.arrastre = None

    # Arma la imagen de la mascara activa o de las tres mascaras juntas
    def _vista_mascaras(self, mascaras):
        if self.vista == 1:
            return cv2.cvtColor(mascaras[self.activo], cv2.COLOR_GRAY2BGR)
        imagen = np.zeros((*mascaras[0].shape, 3), dtype=np.uint8)
        for color, mascara in zip(self.colores, mascaras):
            imagen[mascara != 0] = color.color_bgr
        return imagen

# Procesa una imagen del simulador e imprime en consola la distancia y el angulo
def perception(img):
    interfaz = InterfazPercepcion()
    interfaz.imagen_actual = img
    mascaras, blobs = procesar_imagen(interfaz.imagen_actual, interfaz.colores)
    geometria = calcular_geometria(blobs)
    return geometria
