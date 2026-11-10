import argparse
from pathlib import Path

import cv2
import numpy as np

ANCHO = 1200
ALTO = 720
PANEL = 350
VENTANA = "Detector Blue Square | prueba local"

# Parámetros que se pueden modificar desde el panel izquierdo.
parametros = {
    "H minimo": [90, 0, 179],
    "H maximo": [140, 0, 179],
    "S minimo": [60, 0, 255],
    "S maximo": [255, 0, 255],
    "V minimo": [40, 0, 255],
    "V maximo": [255, 0, 255],
    "Area minima": [150, 0, 5000],
    "Morfologia": [1, 0, 7],
}

imagen_actual = None
centro_objetivo = None
seleccionado = False
mostrar_mascara = False
arrastrando = None
rect_imagen = (PANEL + 20, 100, 810, 590)


def limitar(v, minimo, maximo):
    return max(minimo, min(maximo, v))


def calibrar(imagen, x, y):
    """Estima HSV a partir de una pequeña zona alrededor del clic."""
    global centro_objetivo, seleccionado
    alto, ancho = imagen.shape[:2]
    x, y = limitar(x, 0, ancho - 1), limitar(y, 0, alto - 1)
    radio = 8
    parche = imagen[max(0, y-radio):min(alto, y+radio+1),
                    max(0, x-radio):min(ancho, x+radio+1)]
    hsv = cv2.cvtColor(parche, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    hsv = hsv[(hsv[:, 1] > 35) & (hsv[:, 2] > 25)]
    if len(hsv) < 5:
        print("No hay suficientes píxeles coloreados. Haz clic dentro del cuadrado.")
        return

    bajo = np.percentile(hsv, 10, axis=0)
    alto_hsv = np.percentile(hsv, 90, axis=0)
    valores = [
        int(limitar(np.floor(bajo[0] - 8), 0, 179)),
        int(limitar(np.ceil(alto_hsv[0] + 8), 0, 179)),
        int(limitar(np.floor(bajo[1] - 35), 0, 255)), 255,
        int(limitar(np.floor(bajo[2] - 35), 0, 255)), 255,
    ]
    for nombre, valor in zip(list(parametros)[:6], valores):
        parametros[nombre][0] = valor
    centro_objetivo = (x, y)
    seleccionado = True
    print("Color calibrado. Ahora puedes afinar los seis límites HSV en el panel.")


def procesar(imagen):
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    h0, h1 = sorted([parametros["H minimo"][0], parametros["H maximo"][0]])
    s0, s1 = sorted([parametros["S minimo"][0], parametros["S maximo"][0]])
    v0, v1 = sorted([parametros["V minimo"][0], parametros["V maximo"][0]])
    mascara = cv2.inRange(hsv, np.array([h0, s0, v0]), np.array([h1, s1, v1]))

    nivel = parametros["Morfologia"][0]
    if nivel > 0:
        k = np.ones((2 * nivel + 1, 2 * nivel + 1), np.uint8)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, k)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, k)

    contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidatos = []
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < parametros["Area minima"][0]:
            continue
        x, y, w, h = cv2.boundingRect(contorno)
        if h == 0 or not 0.5 <= w / h <= 2.0:
            continue
        m = cv2.moments(contorno)
        if m["m00"] == 0:
            continue
        centro = (m["m10"] / m["m00"], m["m01"] / m["m00"])
        candidatos.append((area, contorno, (x, y, w, h), centro))

    elegido = None
    if candidatos and seleccionado and centro_objetivo is not None:
        # Favorece el candidato más cercano a la última posición seleccionada.
        elegido = min(candidatos, key=lambda c: np.hypot(
            c[3][0] - centro_objetivo[0], c[3][1] - centro_objetivo[1]))
        centro_objetivo_local = elegido[3]
    else:
        centro_objetivo_local = None

    vista = imagen.copy()
    alto, ancho = vista.shape[:2]
    cv2.line(vista, (ancho // 2, 0), (ancho // 2, alto), (255, 255, 0), 2)
    for candidato in candidatos:
        x, y, w, h = candidato[2]
        cv2.rectangle(vista, (x, y), (x+w, y+h), (0, 165, 255), 1)

    error = None
    if elegido is not None:
        x, y, w, h = elegido[2]
        cx, cy = elegido[3]
        cv2.rectangle(vista, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.circle(vista, (int(cx), int(cy)), 5, (0, 0, 255), -1)
        error = cx - ancho / 2
        cv2.putText(vista, f"Detectado | error x: {error:.1f} px", (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    else:
        mensaje = "Haz clic en el cuadrado azul" if not seleccionado else "Objetivo no detectado"
        cv2.putText(vista, mensaje, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 255), 2)
    return vista, mascara, len(candidatos), error, centro_objetivo_local


def dibujar_boton(canvas, x, y, w, h, texto, activo=False):
    color = (65, 105, 145) if activo else (75, 75, 75)
    cv2.rectangle(canvas, (x, y), (x+w, y+h), color, -1)
    cv2.rectangle(canvas, (x, y), (x+w, y+h), (180, 180, 180), 1)
    cv2.putText(canvas, texto, (x+12, y+25), cv2.FONT_HERSHEY_SIMPLEX,
                0.55, (255, 255, 255), 1, cv2.LINE_AA)


def dibujar_gradiente_hsv(canvas):
    """Dibuja el intervalo HSV como un rectángulo de mínimo a máximo."""
    h_min, h_max = sorted([parametros["H minimo"][0], parametros["H maximo"][0]])
    s_min, s_max = sorted([parametros["S minimo"][0], parametros["S maximo"][0]])
    v_min, v_max = sorted([parametros["V minimo"][0], parametros["V maximo"][0]])

    minimo = np.array([h_min, s_min, v_min], dtype=np.float32)
    maximo = np.array([h_max, s_max, v_max], dtype=np.float32)

    x0, y0 = 18, 620
    ancho, alto = PANEL - 36, 42
    t = np.linspace(0.0, 1.0, ancho, dtype=np.float32)
    valores = minimo + t[:, None] * (maximo - minimo)
    valores = np.clip(np.round(valores), [0, 0, 0], [179, 255, 255])
    colores_hsv = valores.astype(np.uint8).reshape(1, ancho, 3)
    colores_bgr = cv2.cvtColor(colores_hsv, cv2.COLOR_HSV2BGR)
    rectangulo = np.repeat(colores_bgr, alto, axis=0)

    canvas[y0:y0 + alto, x0:x0 + ancho] = rectangulo
    cv2.rectangle(canvas, (x0, y0), (x0 + ancho - 1, y0 + alto - 1),
                  (245, 245, 245), 2)

    texto_min = f"H:{h_min}  S:{s_min}  V:{v_min}"
    texto_max = f"H:{h_max}  S:{s_max}  V:{v_max}"
    cv2.putText(canvas, "MINIMO", (x0, 680), cv2.FONT_HERSHEY_SIMPLEX,
                0.40, (235, 235, 235), 1, cv2.LINE_AA)
    cv2.putText(canvas, "MAXIMO", (x0 + 170, 680), cv2.FONT_HERSHEY_SIMPLEX,
                0.40, (235, 235, 235), 1, cv2.LINE_AA)
    cv2.putText(canvas, texto_min, (x0, 703), cv2.FONT_HERSHEY_SIMPLEX,
                0.36, (100, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, texto_max, (x0 + 170, 703), cv2.FONT_HERSHEY_SIMPLEX,
                0.36, (100, 220, 255), 1, cv2.LINE_AA)


def dibujar_interfaz(imagen, pausado, nombre_frame, candidatos, error):
    canvas = np.full((ALTO, ANCHO, 3), 38, dtype=np.uint8)
    # Panel izquierdo
    cv2.rectangle(canvas, (0, 0), (PANEL, ALTO), (48, 48, 48), -1)
    cv2.putText(canvas, "AJUSTES DE DETECCION", (18, 32), cv2.FONT_HERSHEY_SIMPLEX,
                0.65, (255, 255, 255), 2)
    cv2.putText(canvas, "Mueve los controles y observa los valores", (18, 58),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (205, 205, 205), 1)

    # Controles dibujados: son deslizadores sencillos que responden al mouse.
    y = 105
    for nombre, datos in parametros.items():
        valor, minimo, maximo = datos
        cv2.putText(canvas, nombre, (18, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (240, 240, 240), 1)
        cv2.putText(canvas, str(valor), (PANEL-55, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, (100, 220, 255), 1)
        x0, x1, sy = 20, PANEL-25, y+19
        cv2.line(canvas, (x0, sy), (x1, sy), (110, 110, 110), 5)
        proporcion = (valor-minimo) / max(1, maximo-minimo)
        px = int(x0 + proporcion * (x1-x0))
        cv2.line(canvas, (x0, sy), (px, sy), (70, 190, 255), 5)
        cv2.circle(canvas, (px, sy), 8, (245, 245, 245), -1)
        y += 65

    # Rectángulo degradado: recorre los valores HSV mínimo y máximo.
    cv2.line(canvas, (15, 600), (PANEL-15, 600), (100, 100, 100), 1)
    cv2.putText(canvas, "RANGO HSV: MINIMO A MAXIMO", (18, 616),
                cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1)
    dibujar_gradiente_hsv(canvas)

    # Área derecha: botones y una sola vista (cámara o máscara).
    x0, y0, w, h = rect_imagen
    dibujar_boton(canvas, x0, 25, 170, 42, "VER CAMARA", not mostrar_mascara)
    dibujar_boton(canvas, x0+185, 25, 170, 42, "VER MASCARA", mostrar_mascara)
    dibujar_boton(canvas, x0+370, 25, 130, 42, "REINICIAR HSV")
    dibujar_boton(canvas, x0+515, 25, 130, 42, "LIMPIAR CLICK")

    if mostrar_mascara:
        _, mascara, _, _, _ = procesar(imagen)
        imagen_vista = cv2.cvtColor(mascara, cv2.COLOR_GRAY2BGR)
        titulo = "MASCARA: blanco = pixeles dentro del rango HSV"
    else:
        imagen_vista, _, _, _, _ = procesar(imagen)
        titulo = "CAMARA: haz clic sobre el cuadrado azul para calibrar"
    cv2.putText(canvas, titulo, (x0, 88), cv2.FONT_HERSHEY_SIMPLEX,
                0.48, (235, 235, 235), 1)

    ih, iw = imagen_vista.shape[:2]
    escala = min(w/iw, h/ih)
    nw, nh = int(iw*escala), int(ih*escala)
    reducida = cv2.resize(imagen_vista, (nw, nh))
    canvas[y0:y0+nh, x0:x0+nw] = reducida
    cv2.rectangle(canvas, (x0, y0), (x0+w, y0+h), (130, 130, 130), 1)

    estado = "PAUSADO" if pausado else "REPRODUCIENDO"
    texto_error = "sin deteccion" if error is None else f"error horizontal: {error:.1f} px"
    cv2.putText(canvas, f"{estado} | {nombre_frame} | candidatos: {candidatos} | {texto_error}",
                (x0, 715), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (230, 230, 230), 1)
    return canvas


def mouse(event, x, y, flags, param):
    global arrastrando, mostrar_mascara, centro_objetivo, seleccionado
    imagen = param
    if event == cv2.EVENT_LBUTTONDOWN:
        # Botones de vista y acciones.
        if x > PANEL and 25 <= y <= 67:
            if rect_imagen[0] <= x <= rect_imagen[0]+170:
                mostrar_mascara = False
            elif rect_imagen[0]+185 <= x <= rect_imagen[0]+355:
                mostrar_mascara = True
            elif rect_imagen[0]+370 <= x <= rect_imagen[0]+500:
                for nombre, valor in zip(list(parametros)[:6], [90, 140, 60, 255, 40, 255]):
                    parametros[nombre][0] = valor
            elif rect_imagen[0]+515 <= x <= rect_imagen[0]+645:
                centro_objetivo = None
                seleccionado = False
            return
        # Sliders del panel izquierdo.
        if x < PANEL:
            y_inicio = 124
            for nombre, datos in parametros.items():
                if y_inicio-22 <= y <= y_inicio+12:
                    arrastrando = nombre
                    actualizar_slider(nombre, x)
                    return
                y_inicio += 65
        # Selección del objeto sobre la imagen mostrada.
        if not mostrar_mascara and x >= rect_imagen[0] and y >= rect_imagen[1]:
            rx, ry, rw, rh = rect_imagen
            ih, iw = imagen.shape[:2]
            escala = min(rw/iw, rh/ih)
            nw, nh = int(iw*escala), int(ih*escala)
            if rx <= x < rx+nw and ry <= y < ry+nh:
                ix, iy = int((x-rx)/escala), int((y-ry)/escala)
                calibrar(imagen, ix, iy)
    elif event == cv2.EVENT_MOUSEMOVE and arrastrando is not None:
        actualizar_slider(arrastrando, x)
    elif event == cv2.EVENT_LBUTTONUP:
        arrastrando = None


def actualizar_slider(nombre, x):
    datos = parametros[nombre]
    minimo, maximo = datos[1], datos[2]
    x = limitar(x, 20, PANEL-25)
    proporcion = (x-20)/(PANEL-45)
    datos[0] = int(round(minimo + proporcion*(maximo-minimo)))


def listar_imagenes(carpeta):
    extensiones = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    return sorted([p for p in carpeta.iterdir() if p.suffix.lower() in extensiones])


def main():
    parser = argparse.ArgumentParser(description="Perception")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--images", type=Path, help="Carpeta con imágenes")
    grupo.add_argument("--camera", type=int, help="Índice de webcam, normalmente 0")
    parser.add_argument("--delay", type=int, default=100, help="Tiempo entre imágenes en ms")
    args = parser.parse_args()

    archivos = []
    captura = None
    indice = 0
    pausado = args.images is not None
    if args.images is not None:
        if not args.images.is_dir():
            parser.error("La carpeta indicada no existe")
        archivos = listar_imagenes(args.images)
        if not archivos:
            parser.error("No se encontraron imágenes en la carpeta")
        imagen = cv2.imread(str(archivos[0]))
        if imagen is None:
            parser.error("No se pudo abrir la primera imagen")
    else:
        captura = cv2.VideoCapture(args.camera)
        if not captura.isOpened():
            parser.error("No se pudo abrir la cámara")
        ok, imagen = captura.read()
        if not ok:
            parser.error("No se pudo leer la cámara")
        pausado = False

    global imagen_actual
    imagen_actual = imagen
    cv2.namedWindow(VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(VENTANA, ANCHO, ALTO)
    cv2.setMouseCallback(VENTANA, mouse, imagen_actual)

    try:
        while True:
            if args.images is not None and not pausado:
                indice = (indice+1) % len(archivos)
                nueva = cv2.imread(str(archivos[indice]))
                if nueva is not None:
                    imagen_actual = nueva
                    cv2.setMouseCallback(VENTANA, mouse, imagen_actual)
            elif captura is not None and not pausado:
                ok, nueva = captura.read()
                if ok:
                    imagen_actual = nueva
                    cv2.setMouseCallback(VENTANA, mouse, imagen_actual)

            vista, mascara, n_candidatos, error, centro = procesar(imagen_actual)
            if centro is not None:
                global centro_objetivo
                centro_objetivo = centro
            nombre = archivos[indice].name if args.images is not None else "webcam"
            interfaz = dibujar_interfaz(imagen_actual, pausado, nombre, n_candidatos, error)
            cv2.imshow(VENTANA, interfaz)
            espera = max(1, args.delay) if not pausado and args.images is not None else 25
            tecla = cv2.waitKey(espera) & 0xFF
            if tecla in (ord('q'), 27):
                break
            if tecla == ord(' '):
                pausado = not pausado
            elif tecla == ord('n') and args.images is not None:
                pausado = True
                indice = (indice+1) % len(archivos)
                imagen_actual = cv2.imread(str(archivos[indice]))
                cv2.setMouseCallback(VENTANA, mouse, imagen_actual)
            elif tecla == ord('c'):
                centro_objetivo = None
                seleccionado = False
            elif tecla == ord('r'):
                for nombre, valor in zip(list(parametros)[:6], [90, 140, 60, 255, 40, 255]):
                    parametros[nombre][0] = valor
    finally:
        if captura is not None:
            captura.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
