import argparse
import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


ANCHO_VENTANA = 1280
ALTO_VENTANA = 780 + 100  ########## Ajustar alto ventana ##################
ANCHO_PANEL = 370
NOMBRE_VENTANA = "Perception"

AREA_MINIMA_PX = 80
TAM_KERNEL = 3
KERNEL = np.ones((TAM_KERNEL, TAM_KERNEL), dtype=np.uint8)

# En H (tono), si el minimo supera el maximo, el intervalo cruza por H=0.
RANGOS_INICIALES = [
    ("DELANTE", (0, 0, 255), {"H": [170, 10], "S": [85, 255], "V": [60, 255]}),
    ("ATRÁS", (255, 0, 0), {"H": [95, 135], "S": [70, 255], "V": [50, 255]}),
    ("BALON", (0, 255, 255), {"H": [20, 40], "S": [85, 255], "V": [90, 255]}),
]

LIMITES_HSV = {"H": 179, "S": 255, "V": 255}
SLIDER_X0 = 26
SLIDER_X1 = ANCHO_PANEL - 30
SLIDER_Y = {"H": 258, "S": 365, "V": 472}
RECT_PESTANAS = (18, 94, ANCHO_PANEL - 18, 138)
RECT_VISTA = (ANCHO_PANEL + 22, 155, ANCHO_VENTANA - 22, 708)


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


@dataclass
class Blob:
    recuadro: Tuple[int, int, int, int]  # x, y, ancho, alto
    centro: Tuple[float, float]          
    area: int

def crear_mascara(hsv: np.ndarray, rangos: Dict[str, List[int]]) -> np.ndarray:
    h0, h1 = rangos["H"]
    s0, s1 = rangos["S"]
    v0, v1 = rangos["V"]

    if h0 <= h1:
        mascara = cv2.inRange(hsv, (h0, s0, v0), (h1, s1, v1))
    else:
        superior = cv2.inRange(hsv, (h0, s0, v0), (179, s1, v1))
        inferior = cv2.inRange(hsv, (0, s0, v0), (h1, s1, v1))
        mascara = cv2.bitwise_or(superior, inferior)

    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, KERNEL)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, KERNEL)
    return mascara


def buscar_blob_principal(mascara: np.ndarray) -> Optional[Blob]:
    cantidad, _, estadisticas, centroides = cv2.connectedComponentsWithStats(
        mascara, connectivity=8
    )
    if cantidad <= 1:
        return None

    # 0 corresponde al fondo, no considerar.
    areas = estadisticas[1:, cv2.CC_STAT_AREA]
    indice = 1 + int(np.argmax(areas))
    area = int(estadisticas[indice, cv2.CC_STAT_AREA])
    if area < AREA_MINIMA_PX:
        return None

    x = int(estadisticas[indice, cv2.CC_STAT_LEFT])
    y = int(estadisticas[indice, cv2.CC_STAT_TOP])
    ancho = int(estadisticas[indice, cv2.CC_STAT_WIDTH])
    alto = int(estadisticas[indice, cv2.CC_STAT_HEIGHT])
    cx, cy = centroides[indice]
    return Blob((x, y, ancho, alto), (float(cx), float(cy)), area)


def procesar_imagen(imagen: np.ndarray, colores: List[ColorConfig]):
    hsv = cv2.cvtColor(imagen, cv2.COLOR_BGR2HSV)
    mascaras = []
    blobs = []

    for color in colores:
        mascara = crear_mascara(hsv, color.rangos)
        mascaras.append(mascara)
        blobs.append(buscar_blob_principal(mascara))

    return mascaras, blobs


def anotar_detecciones(imagen: np.ndarray, colores: List[ColorConfig],
                       blobs: List[Optional[Blob]]) -> np.ndarray:
    salida = imagen.copy()
    alto_img, ancho_img = salida.shape[:2]

    for color, blob in zip(colores, blobs):
        if blob is None:
            continue

        x, y, w, h = blob.recuadro
        cx, cy = blob.centro
        color_bgr = color.color_bgr
        cv2.rectangle(salida, (x, y), (x + w - 1, y + h - 1), color_bgr, 2)

        texto = f"({cx:.0f}, {cy:.0f})"
        fuente, escala, grosor = cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2
        (ancho_texto, alto_texto), _ = cv2.getTextSize(texto, fuente, escala, grosor)
        tx = max(2, min(x, ancho_img - ancho_texto - 3))
        ty = y - 7 if y >= alto_texto + 10 else min(alto_img - 4, y + h + alto_texto + 5)

        cv2.putText(salida, texto, (tx, ty), fuente, escala, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(salida, texto, (tx, ty), fuente, escala, color_bgr, grosor, cv2.LINE_AA)

    return salida


def calibrar_hsv_por_click(imagen: np.ndarray, x: int, y: int):

    alto, ancho = imagen.shape[:2]
    radio = 6
    x0, x1 = max(0, x - radio), min(ancho, x + radio + 1)
    y0, y1 = max(0, y - radio), min(alto, y + radio + 1)
    muestras = cv2.cvtColor(imagen[y0:y1, x0:x1], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    muestras = muestras[(muestras[:, 1] > 35) & (muestras[:, 2] > 25)]
    if len(muestras) < 8:
        return None

    tonos = muestras[:, 0].astype(np.float32)
    angulos = tonos * (2.0 * np.pi / 180.0)
    promedio = np.arctan2(np.sin(angulos).mean(), np.cos(angulos).mean())
    centro_tono = (promedio % (2.0 * np.pi)) * 180.0 / (2.0 * np.pi)
    diferencias = (tonos - centro_tono + 90.0) % 180.0 - 90.0
    h_min = int(np.floor(centro_tono + np.percentile(diferencias, 10) - 7)) % 180
    h_max = int(np.ceil(centro_tono + np.percentile(diferencias, 90) + 7)) % 180

    s_min = int(max(0, np.floor(np.percentile(muestras[:, 1], 10) - 30)))
    s_max = int(min(255, np.ceil(np.percentile(muestras[:, 1], 90) + 30)))
    v_min = int(max(0, np.floor(np.percentile(muestras[:, 2], 10) - 35)))
    v_max = int(min(255, np.ceil(np.percentile(muestras[:, 2], 90) + 35)))

    return {"H": [h_min, h_max], "S": [s_min, s_max], "V": [v_min, v_max]}

def escribir(canvas, texto, x, y, escala=0.50, color=(235, 235, 235), grosor=1):
    cv2.putText(canvas, texto, (int(x), int(y)), cv2.FONT_HERSHEY_SIMPLEX,
                escala, color, grosor, cv2.LINE_AA)


def limitar(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


class InterfazPercepcion:
    def __init__(self):
        self.colores = [ColorConfig(*datos) for datos in RANGOS_INICIALES]
        self.activo = 0
        # V: 0 = camara, 1 = mascara activa, 2 = union de las tres mascaras.
        self.vista = 0
        self.imagen_actual = None
        self.area_imagen_real = (0, 0, 0, 0)
        self.arrastre = None
        self.mensaje = "Click en la imagen: calibrar el color seleccionado"

    @property
    def color_actual(self):
        return self.colores[self.activo]

    def _slider_x(self, valor, componente):
        return int(round(SLIDER_X0 + (valor / LIMITES_HSV[componente])
                         * (SLIDER_X1 - SLIDER_X0)))

    def _actualizar_slider(self, componente, extremo, x):
        x = limitar(x, SLIDER_X0, SLIDER_X1)
        maximo = LIMITES_HSV[componente]
        valor = int(round((x - SLIDER_X0) * maximo / (SLIDER_X1 - SLIDER_X0)))
        par = self.color_actual.rangos[componente]

        if componente == "H":
            par[extremo] = valor
        elif extremo == 0:
            par[0] = min(valor, par[1])
        else:
            par[1] = max(valor, par[0])

    def _dibujar_pestanas(self, canvas):
        x_inicial, y0, x_final, y1 = RECT_PESTANAS
        ancho = (x_final - x_inicial - 16) // 3
        for indice, color in enumerate(self.colores):
            x = x_inicial + indice * (ancho + 8)
            activo = indice == self.activo
            fondo = (72, 73, 80) if activo else (48, 49, 54)
            cv2.rectangle(canvas, (x, y0), (x + ancho, y1), fondo, -1)
            cv2.rectangle(canvas, (x, y0), (x + ancho, y1),
                          color.color_bgr if activo else (96, 96, 102), 2 if activo else 1)
            escribir(canvas, color.nombre, x + 8, y0 + 26,
                     escala=0.42, color=(255, 255, 255), grosor=1)
            cv2.circle(canvas, (x + ancho - 8, y0 + 10), 4, color.color_bgr, -1)

    def _dibujar_slider(self, canvas, componente):
        bajo, alto = self.color_actual.rangos[componente]
        y = SLIDER_Y[componente]
        escribir(canvas, f"{componente} - " + {"H": "Tono", "S": "Saturacion", "V": "Brillo"}[componente],
                 22, y - 34, 0.52, (245, 245, 245))
        escribir(canvas, f"{bajo} - {alto}", 240, y - 34, 0.48, (125, 220, 255))
        cv2.line(canvas, (SLIDER_X0, y), (SLIDER_X1, y), (95, 95, 103), 6)
        x_bajo = self._slider_x(bajo, componente)
        x_alto = self._slider_x(alto, componente)

        if bajo <= alto:
            cv2.line(canvas, (x_bajo, y), (x_alto, y), (115, 210, 255), 6)
        else:
            # Visualiza el rango circular de H como dos segmentos extremos.
            cv2.line(canvas, (SLIDER_X0, y), (x_alto, y), (115, 210, 255), 6)
            cv2.line(canvas, (x_bajo, y), (SLIDER_X1, y), (115, 210, 255), 6)

        cv2.circle(canvas, (x_bajo, y), 10, (252, 252, 252), -1)
        cv2.circle(canvas, (x_bajo, y), 10, (40, 40, 40), 1)
        cv2.circle(canvas, (x_alto, y), 8, (25, 175, 252), -1)
        cv2.circle(canvas, (x_alto, y), 8, (250, 250, 250), 1)
        escribir(canvas, "MIN: punto blanco", SLIDER_X0, y + 26, 0.35, (190, 190, 198))
        escribir(canvas, "MAX: punto naranja", SLIDER_X1 - 133, y + 26, 0.35,
                 (190, 190, 198))

    def _dibujar_gradiente(self, canvas):
        rangos = self.color_actual.rangos
        ancho, alto = ANCHO_PANEL - 44, 38
        h0, h1 = rangos["H"]
        s0, s1 = rangos["S"]
        v0, v1 = rangos["V"]
        fraccion = np.linspace(0, 1, ancho, dtype=np.float32)
        delta_h = (h1 - h0) % 180
        h = (h0 + fraccion * delta_h) % 180
        s = s0 + fraccion * (s1 - s0)
        v = v0 + fraccion * (v1 - v0)
        linea_hsv = np.stack((h, s, v), axis=1).round().astype(np.uint8)
        linea_bgr = cv2.cvtColor(linea_hsv[np.newaxis, :, :], cv2.COLOR_HSV2BGR)
        gradiente = np.repeat(linea_bgr, alto, axis=0)
        canvas[562:562 + alto, 22:22 + ancho] = gradiente
        cv2.rectangle(canvas, (22, 562), (22 + ancho, 562 + alto), (210, 210, 210), 1)
        escribir(canvas, "PREVISUALIZACION DEL RANGO HSV", 22, 543, 0.43)
        escribir(canvas, f"MIN: H{h0}  S{s0}  V{v0}", 22, 622, 0.37, (190, 195, 204))
        escribir(canvas, f"MAX: H{h1}  S{s1}  V{v1}", 185, 622, 0.37, (190, 195, 204))

    def _vista_mascaras(self, mascaras):
        if self.vista == 1:
            return cv2.cvtColor(mascaras[self.activo], cv2.COLOR_GRAY2BGR)
        imagen = np.zeros((*mascaras[0].shape, 3), dtype=np.uint8)
        for color, mascara in zip(self.colores, mascaras):
            imagen[mascara != 0] = color.color_bgr
        return imagen

    def dibujar(self, imagen, mascaras, blobs, pausado, nombre):
        canvas = np.full((ALTO_VENTANA, ANCHO_VENTANA, 3), 34, dtype=np.uint8)
        cv2.rectangle(canvas, (0, 0), (ANCHO_PANEL, ALTO_VENTANA), (48, 49, 54), -1)
        escribir(canvas, "PERCEPTION", 19, 38, 0.70, (255, 255, 255), 2)
        self._dibujar_pestanas(canvas)
        escribir(canvas, self.color_actual.nombre, 21, 176, 0.53, (246, 246, 246))

        for componente in ("H", "S", "V"):
            self._dibujar_slider(canvas, componente)
        self._dibujar_gradiente(canvas)

        cv2.line(canvas, (20, 649), (ANCHO_PANEL - 20, 649), (98, 98, 102), 1)

        escribir(canvas, self.mensaje[:42], 22, 750, 0.37, (205, 205, 210))

        x_left = ANCHO_PANEL + 23
        escribir(canvas, "[1-3] Color   [V] Vista   [R] Reiniciar HSV   [C] Deshacer clic",
                 x_left, 35, 0.49, (250, 250, 250))
        escribir(canvas, "[ESPACIO] Pausar   [N] Siguiente imagen   [Q/ESC] Salir",
                 x_left, 65, 0.49, (215, 215, 222))

        if self.vista == 0:
            mostrada = anotar_detecciones(imagen, self.colores, blobs)
        else:
            mostrada = self._vista_mascaras(mascaras)

        ix0, iy0, ix1, iy1 = RECT_VISTA
        ancho_region, alto_region = ix1 - ix0, iy1 - iy0
        alto_original, ancho_original = mostrada.shape[:2]
        escala = min(ancho_region / ancho_original, alto_region / alto_original)
        ancho_nuevo = max(1, int(round(ancho_original * escala)))
        alto_nuevo = max(1, int(round(alto_original * escala)))
        ox = ix0 + (ancho_region - ancho_nuevo) // 2
        oy = iy0 + (alto_region - alto_nuevo) // 2
        reducida = cv2.resize(mostrada, (ancho_nuevo, alto_nuevo),
                              interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_LINEAR)
        canvas[oy:oy + alto_nuevo, ox:ox + ancho_nuevo] = reducida
        self.area_imagen_real = (ox, oy, ancho_nuevo, alto_nuevo)
        cv2.rectangle(canvas, (ix0, iy0), (ix1, iy1), (100, 100, 105), 1)

        detectados = sum(blob is not None for blob in blobs)
        estado = "PAUSADO" if pausado else "REPRODUCIENDO"
        nombre = nombre if len(nombre) < 75 else "..." + nombre[-72:]
        escribir(canvas, f"{estado}  |  {nombre}  |  Objetos localizados: {detectados}/3",
                 ix0, 747, 0.46, (225, 225, 225))
        return canvas

    def mouse(self, evento, x, y, flags, param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            p_x0, p_y0, p_x1, p_y1 = RECT_PESTANAS
            if p_x0 <= x <= p_x1 and p_y0 <= y <= p_y1:
                ancho = (p_x1 - p_x0 - 16) // 3
                for i in range(3):
                    izquierda = p_x0 + i * (ancho + 8)
                    if izquierda <= x <= izquierda + ancho:
                        self.activo = i
                        self.arrastre = None
                        self.mensaje = f"Configurando: {self.color_actual.nombre}"
                        return

            if SLIDER_X0 - 15 <= x <= SLIDER_X1 + 15:
                for componente, sy in SLIDER_Y.items():
                    if abs(y - sy) <= 16:
                        minimo, maximo = self.color_actual.rangos[componente]
                        posicion_min = self._slider_x(minimo, componente)
                        posicion_max = self._slider_x(maximo, componente)
                        extremo = 0 if abs(x - posicion_min) <= abs(x - posicion_max) else 1
                        self.arrastre = (componente, extremo)
                        self._actualizar_slider(componente, extremo, x)
                        return

            if self.vista != 0 or self.imagen_actual is None:
                return
            ox, oy, w, h = self.area_imagen_real
            if ox <= x < ox + w and oy <= y < oy + h:
                alto_img, ancho_img = self.imagen_actual.shape[:2]
                ix = limitar(int((x - ox) * ancho_img / w), 0, ancho_img - 1)
                iy = limitar(int((y - oy) * alto_img / h), 0, alto_img - 1)
                rangos = calibrar_hsv_por_click(self.imagen_actual, ix, iy)
                if rangos is None:
                    self.mensaje = "Click sin suficientes pixeles de color"
                else:
                    color = self.color_actual
                    color.previo_al_click = copy.deepcopy(color.rangos)
                    color.rangos = rangos
                    color.ultimo_click = (ix, iy)
                    self.mensaje = f"{color.nombre}: HSV calibrado desde clic"

        elif evento == cv2.EVENT_MOUSEMOVE and self.arrastre is not None:
            componente, extremo = self.arrastre
            self._actualizar_slider(componente, extremo, x)
        elif evento == cv2.EVENT_LBUTTONUP:
            self.arrastre = None

    def tecla(self, codigo):
        if codigo in (ord("q"), 27):
            return False
        if codigo in (ord("1"), ord("2"), ord("3")):
            self.activo = codigo - ord("1")
            self.mensaje = f"Configurando: {self.color_actual.nombre}"
        elif codigo == ord("v"):
            self.vista = (self.vista + 1) % 3
        elif codigo == ord("r"):
            self.color_actual.reiniciar()
            self.mensaje = f"HSV reiniciado: {self.color_actual.nombre}"
        elif codigo == ord("c"):
            color = self.color_actual
            if color.previo_al_click is not None:
                color.rangos = color.previo_al_click
                color.previo_al_click = None
                color.ultimo_click = None
                self.mensaje = "Ultimo clic deshecho (HSV recuperado)"
            else:
                color.ultimo_click = None
                self.mensaje = "No hay clic de calibracion para deshacer"
        return True


def listar_imagenes(carpeta: Path) -> List[Path]:
    extensiones = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
    return sorted(p for p in carpeta.iterdir() if p.is_file() and p.suffix.lower() in extensiones)


def abrir_imagen(ruta: Path):
    try:
        return cv2.imdecode(np.fromfile(str(ruta), dtype=np.uint8), cv2.IMREAD_COLOR)
    except (OSError, ValueError, cv2.error):
        return None


def main():
    parser = argparse.ArgumentParser(description="Perception")
    fuente = parser.add_mutually_exclusive_group(required=True)
    fuente.add_argument("--camera", type=int, metavar="N", help="Indice de la camara (0 o 1)")
    fuente.add_argument("--images", type=Path, metavar="CARPETA", help="Carpeta de imagenes")
    fuente.add_argument("--image", type=Path, metavar="FOTO", help="Una imagen individual")
    parser.add_argument("--delay", type=int, default=500,
                        help="Milisegundos entre fotos al reproducir una carpeta (default: 500)")
    args = parser.parse_args()

    captura = None
    archivos = []
    indice = 0
    pausado = args.camera is None

    if args.camera is not None:
        captura = (cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
                   if os.name == "nt" else cv2.VideoCapture(args.camera))
        if not captura.isOpened():
            parser.error("No se pudo abrir la camara. Prueba con --camera 0 o 1")
        ok, imagen = captura.read()
        if not ok or imagen is None:
            captura.release()
            parser.error("No se pudo leer una imagen de la camara")
    else:
        if args.images is not None:
            if not args.images.is_dir():
                parser.error("La carpeta indicada no existe")
            archivos = listar_imagenes(args.images)
        else:
            archivos = [args.image]
        if not archivos:
            parser.error("No hay archivos de imagen compatibles")
        imagen = abrir_imagen(archivos[0])
        if imagen is None:
            parser.error(f"No se pudo abrir la imagen: {archivos[0]}")

    interfaz = InterfazPercepcion()
    interfaz.imagen_actual = imagen
    cv2.namedWindow(NOMBRE_VENTANA, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(NOMBRE_VENTANA, ANCHO_VENTANA, ALTO_VENTANA)
    cv2.setMouseCallback(NOMBRE_VENTANA, interfaz.mouse)

    try:
        while True:
            if captura is not None and not pausado:
                ok, nueva = captura.read()
                if ok and nueva is not None:
                    interfaz.imagen_actual = nueva
                else:
                    interfaz.mensaje = "No se pudo leer un frame de la camara"
            elif archivos and not pausado and len(archivos) > 1:
                siguiente = (indice + 1) % len(archivos)
                nueva = abrir_imagen(archivos[siguiente])
                if nueva is not None:
                    indice = siguiente
                    interfaz.imagen_actual = nueva
                else:
                    indice = siguiente
                    interfaz.mensaje = "No se pudo cargar una imagen de la carpeta"

            mascaras, blobs = procesar_imagen(interfaz.imagen_actual, interfaz.colores)
            nombre = archivos[indice].name if archivos else f"Camara {args.camera}"
            canvas = interfaz.dibujar(interfaz.imagen_actual, mascaras, blobs, pausado, nombre)
            cv2.imshow(NOMBRE_VENTANA, canvas)

            espera = max(1, args.delay) if archivos and not pausado else 25
            tecla = cv2.waitKey(espera) & 0xFF
            if not interfaz.tecla(tecla):
                break
            if tecla == ord(" "):
                pausado = not pausado
            elif tecla == ord("n") and archivos:
                pausado = True
                siguiente = (indice + 1) % len(archivos)
                nueva = abrir_imagen(archivos[siguiente])
                if nueva is not None:
                    indice = siguiente
                    interfaz.imagen_actual = nueva
                else:
                    interfaz.mensaje = f"No se pudo leer: {archivos[siguiente].name}"

            if cv2.getWindowProperty(NOMBRE_VENTANA, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        if captura is not None:
            captura.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
