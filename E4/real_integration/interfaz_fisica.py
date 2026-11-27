# Superposición de estado original sobre la interfaz de percepción
import cv2
from perception import ANCHO_PANEL, ANCHO_VENTANA


def pintar_estado(canvas, armado, modo, fase, estado, ruedas, mensaje):
    inicio = ANCHO_PANEL + 18
    cv2.rectangle(canvas, (inicio, 4), (ANCHO_VENTANA - 8, 85), (34, 34, 34), -1)
    cv2.putText(canvas, "[ESPACIO] ARMAR/PAUSAR  [S] GUARDAR HSV  [1-3] COLOR  [V] VISTA",
                (inicio + 6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (245, 245, 245), 1, cv2.LINE_AA)
    cv2.putText(canvas, "[R] RESTABLECER HSV  [C] DESHACER CLICK  [Q/ESC] PARAR Y SALIR",
                (inicio + 6, 59), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (220, 220, 225), 1, cv2.LINE_AA)
    cv2.rectangle(canvas, (inicio, 712), (ANCHO_VENTANA - 8, 774), (34, 34, 34), -1)
    pausa_visual = armado and estado is None
    situacion = "ARMADO/PAUSA" if pausa_visual else ("ACTIVO" if armado else "PARADO")
    if estado is None:
        pos = "Sin marcadores: orden 0,0"
    else:
        pos = f"Distancia libre: {estado[0]:.1f}px   |   Angulo: {estado[1]:+.1f} grados"
    cv2.putText(canvas, f"{modo}  |  {situacion}  |  {fase}  |  RPM: {ruedas[0]}, {ruedas[1]}",
                (inicio + 6, 733), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (0, 185, 255) if pausa_visual else ((90, 220, 90) if armado else (150, 185, 255)),
                1, cv2.LINE_AA)
    cv2.putText(canvas, (mensaje or pos)[:110], (inicio + 6, 759),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (230, 230, 230), 1, cv2.LINE_AA)
    return canvas

