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
DISTANCIA_SEGURA_PX = 10.0

# Ganancias
KP_GIRO = 0.07579
KI_GIRO = 0.000
KD_GIRO = 0.00012
KP_AVANCE = 0.09049
KI_AVANCE = 0.0
KD_AVANCE = 0.00289

# Límites de velocidad de rueda (rad/s)
MAX_AVANCE = 150.0
MAX_GIRO = 50.0

# Histéresis temporal
TOLERANCIA_ANGULO_GRADOS = 1.5
FRAMES_ALINEADO = 2
VELOCIDAD_GIRO_CASI_CERO = 0.3

TOLERANCIA_DISTANCIA_PX = 1.5
FRAMES_DETENIDO = 5
VELOCIDAD_AVANCE_CASI_CERO = 0.13


# Parámetros integración física

# Distancia del centro del marcador delantero al borde REAL del robot en
# dirección de marcha, en píxeles de la imagen original.
OFFSET_FRENTE_PX = 0.0

# Escala de velocidad para pruebas. 1.0 = conversión rad/s -> RPM pura.
ESCALA_VELOCIDAD_FISICA = 1.0
MAX_RPM_FISICO = 100.0
RAMPA_RPM_POR_S = 45.0  # Limita cambios de referencia entre frames
INTERVALO_ENVIO_BT_S = 0.15  # Muy inferior al timeout Arduino (1.5 s)
MAX_SIN_ACK_S = 1.5  # Pierde habilitación si no hay respuesta del Arduino
MAX_DT_CONTROL_S = 1.0  # Ciclo de cámara demasiado lento -> frenar y rearmar

# Tolerancia de pérdida visual: motores detenidos, pero robot aún armado.
TIEMPO_MAX_SIN_DETECCION_S = 1.5
