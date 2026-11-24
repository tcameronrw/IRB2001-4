# Segmentación HSV
AREA_MINIMA_PX = 80
TAM_KERNEL = 3

# Formato: nombre, color de visualización BGR, umbrales HSV.
RANGOS_INICIALES = [
    ("DELANTE", (255, 0, 0), {"H": [112, 126], "S": [206, 255], "V": [202, 255]}),
    ("ATRAS", (0, 0, 255), {"H": [170, 10], "S": [85, 255], "V": [60, 255]}),
    ("BALON", (0, 255, 255), {"H": [20, 40], "S": [85, 255], "V": [90, 255]}),
]

# Distancia entre el centro de delante y el balón.
DISTANCIA_SEGURA_PX = 70.0

# Ganancias
KP_GIRO = 0.07579
KI_GIRO = 0.000
KD_GIRO = 0.00012
KP_AVANCE = 0.09049
KI_AVANCE = 0.0
KD_AVANCE = 0.00289

# Límites de velocidad de rueda (rad/s)
MAX_AVANCE = 150.0

# Histéresis temporal
TOLERANCIA_ANGULO_GRADOS = 0.5
FRAMES_ALINEADO = 3
VELOCIDAD_GIRO_CASI_CERO = 0.2

TOLERANCIA_DISTANCIA_PX = 0.9
FRAMES_DETENIDO = 8
VELOCIDAD_AVANCE_CASI_CERO = 0.13