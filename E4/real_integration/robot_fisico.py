import argparse
import math
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import cv2
import parameters as par
from comunicacion import BluetoothE1, LimitadorRampa, convertir_a_rpm
from perception import (ColorConfig, InterfazPercepcion, procesar_imagen,
                        ANCHO_VENTANA, ALTO_VENTANA, escala_ventana_para_pantalla)
from geometria import estado_robot
from calibracion import guardar_colores, cargar_colores
from camara import abrir_camara
from interfaz_fisica import pintar_estado
from cancha import construir_estado
from rutinas.tipos import EN_CURSO, COMPLETADA, PENDIENTE


def ejecutar(args):
    try:
        from rutinas.gestor import GestorRutinas
    except ImportError as exc:
        raise RuntimeError("Falta simple-pid. Ejecuta pip install -r requirements.txt") from exc

    tolerancia_vision = float(par.TIEMPO_MAX_SIN_DETECCION_S)
    if not math.isfinite(tolerancia_vision) or tolerancia_vision < 0:
        raise ValueError("TIEMPO_MAX_SIN_DETECCION_S debe ser finito y no negativo")

    gestor = GestorRutinas(args.modo, args.rutinas)
    interfaz = InterfazPercepcion()
    interfaz.colores = [ColorConfig(*dato) for dato in par.RANGOS_INICIALES]
    if cargar_colores(args.hsv, interfaz.colores):
        print(f"HSV cargado desde {args.hsv}")
    gestor.reiniciar()
    limitador = LimitadorRampa(par.RAMPA_RPM_POR_S)
    cap = abrir_camara(args.camera)
    serial_contexto = nullcontext(None) if args.dry_run else BluetoothE1(
        args.port, intervalo=par.INTERVALO_ENVIO_BT_S)
    armado = False
    perdida_desde = None  # Instante de la primera detección inválida consecutiva.
    mensaje = "Verifica los 3 marcadores. ESPACIO para iniciar."
    ultima_iteracion = time.monotonic()
    ultima_impresion = 0.0
    escala_ventana = escala_ventana_para_pantalla()
    cv2.namedWindow("IRB2001 - E4", cv2.WINDOW_AUTOSIZE)

    def mouse_escalado(evento, x, y, flags, param):
        # No permitir editar selección/máscaras con los motores en marcha.
        nonlocal armado, mensaje
        if evento == cv2.EVENT_LBUTTONDOWN and armado:
            armado = False
            gestor.reiniciar()
            limitador.detener()
            if enlace is not None:
                enlace.detener()
            mensaje = "Edicion HSV: movimiento detenido"
        interfaz.mouse(evento, int(x / escala_ventana), int(y / escala_ventana), flags, param)
    cv2.setMouseCallback("IRB2001 - E4", mouse_escalado)

    try:
        with serial_contexto as enlace:
            if enlace is not None:
                print(f"Comprobando respuesta Bluetooth de Arduino en {args.port}...")
                if not enlace.verificar_enlace():
                    raise RuntimeError(
                        "No llegó respuesta OK del Arduino. Verifica puerto COM de salida, "
                        "emparejamiento"
                    )
                print(f"Arduino confirmó: {enlace.ultima_respuesta}")
            else:
                print("MODO PRUEBA: no se enviarán órdenes a los motores.")

            while True:
                ahora = time.monotonic()
                dt = ahora - ultima_iteracion
                ultima_iteracion = ahora
                ok, frame = cap.read()
                if not ok or frame is None:
                    armado = False
                    gestor.reiniciar()
                    if enlace is not None:
                        enlace.detener()
                    raise RuntimeError("Se perdió la cámara. Órdenes detenidas.")

                interfaz.imagen_actual = frame
                mascaras, blobs = procesar_imagen(frame, interfaz.colores)
                estado = estado_robot(blobs, interfaz.colores, par.OFFSET_FRENTE_PX)
                cancha = construir_estado(frame, blobs, interfaz.colores, estado)

                if enlace is not None:
                    for respuesta in enlace.leer_respuestas():
                        if respuesta.startswith(("ERR", "STOP")):
                            mensaje = "Bluetooth: " + respuesta
                            armado = False
                            gestor.reiniciar()
                    if (enlace.ultimo_ack is None
                            or ahora - enlace.ultimo_ack > par.MAX_SIN_ACK_S):
                        armado = False
                        gestor.reiniciar()
                        mensaje = "Sin confirmacion Bluetooth: desarmado"

                if dt > par.MAX_DT_CONTROL_S:
                    armado = False
                    gestor.reiniciar()
                    mensaje = "Ciclo lento / bloqueo de camara: desarmado"

                if not armado:
                    perdida_desde = None
                elif estado is None or perdida_desde is not None:
                    instante_vision = time.monotonic()
                    if perdida_desde is None:
                        perdida_desde = instante_vision
                        gestor.reiniciar_rutina_actual()

                    tiempo_sin_deteccion = instante_vision - perdida_desde
                    if tiempo_sin_deteccion >= tolerancia_vision:
                        armado = False
                        perdida_desde = None
                        mensaje = "Tiempo sin deteccion agotado: ESPACIO para rearmar"
                    elif estado is not None:
                        perdida_desde = None
                        mensaje = "Deteccion recuperada: reanudacion automatica"
                    else:
                        mensaje = (f"Sin deteccion: {tiempo_sin_deteccion:.2f}/"
                                   f"{tolerancia_vision:.2f}s; esperando marcadores")

                if armado and estado is not None:
                    resultado = gestor.actualizar(cancha, dt=max(0.001, dt))
                    fase = resultado.fase
                    if resultado.estado == EN_CURSO:
                        rpms = convertir_a_rpm(resultado.u, resultado.v,
                                              par.ESCALA_VELOCIDAD_FISICA,
                                              par.MAX_RPM_FISICO)
                        ruedas = limitador.aplicar(rpms, dt)
                    else:
                        # No aplicar rampa al finalizar, esperar o cambiar de rutina.
                        ruedas = limitador.detener()
                        if resultado.estado in (COMPLETADA, PENDIENTE):
                            armado = False
                            mensaje = ("Rutina o secuencia completada: detenido"
                                       if resultado.estado == COMPLETADA
                                       else fase)
                elif armado:
                    # Sin percepción válida: cero inmediato, sin perder el paso actual.
                    ruedas = limitador.detener()
                    fase = "PAUSA VISUAL"
                else:
                    gestor.reiniciar()
                    ruedas = limitador.detener()
                    fase = "SIN DETECCION" if estado is None else "EN ESPERA"

                if enlace is not None:
                    enlace.enviar(*ruedas)

                if ahora - ultima_impresion >= 1.0:
                    print(f"{fase:>15s} | estado={estado} | RPM={ruedas} | armado={armado}")
                    ultima_impresion = ahora

                canvas = interfaz.dibujar(frame, mascaras, blobs,
                                          pausado=not armado or estado is None, nombre="Robot fisico",
                                          geometria=estado)
                pintar_estado(canvas, armado, f"{args.modo.upper()} / " + ("SIN MOTORES" if args.dry_run else "BLUETOOTH"),
                              fase, estado, ruedas, mensaje)
                if escala_ventana < 1.0:
                    canvas = cv2.resize(canvas,
                                        (round(ANCHO_VENTANA * escala_ventana),
                                         round(ALTO_VENTANA * escala_ventana)),
                                        interpolation=cv2.INTER_AREA)
                cv2.imshow("IRB2001 - E4", canvas)
                tecla = cv2.waitKey(1) & 0xFF
                if tecla == 32:  # espacio
                    if armado:
                        armado = False
                        gestor.reiniciar()
                        limitador.detener()
                        if enlace is not None:
                            enlace.detener()
                        mensaje = "Movimiento pausado por usuario"
                    elif estado is not None and (
                            enlace is None or (enlace.ultimo_ack is not None
                                and time.monotonic() - enlace.ultimo_ack < par.MAX_SIN_ACK_S)):
                        armado = True
                        perdida_desde = None
                        gestor.reiniciar()
                        limitador.detener()
                        mensaje = f"Modo {args.modo}: habilitado"
                    else:
                        mensaje = "No armar: detecta 3 objetos y confirma Bluetooth"
                elif tecla in (ord('1'), ord('2'), ord('3'), ord('r'), ord('c'), ord('v'), ord('s')) and armado:
                    armado = False
                    gestor.reiniciar()
                    limitador.detener()
                    if enlace is not None:
                        enlace.detener()
                    mensaje = "Calibracion: movimiento detenido"
                if tecla == ord('s'):
                    guardar_colores(args.hsv, interfaz.colores)
                    mensaje = f"HSV guardado en {args.hsv.name}"
                    print(mensaje)
                if not interfaz.tecla(tecla):
                    break
                if cv2.getWindowProperty("IRB2001 - E4", cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Salida: orden de parada enviada (si había Bluetooth).")



def main():
    parser = argparse.ArgumentParser(description="Integración E4 con robot real")
    parser.add_argument('--port', help='Puerto Bluetooth de salida, ej. COM20')
    parser.add_argument('--camera', type=int, default=0, help='Cámara cenital (0 o 1)')
    parser.add_argument('--dry-run', action='store_true', help='Analizar imagen sin motores ni Bluetooth')
    parser.add_argument('--hsv', type=Path,
                        default=Path(__file__).resolve().with_name('calibracion_hsv.json'),
                        help='Ruta donde leer/guardar rangos HSV')
    parser.add_argument('--modo', choices=('manual', 'automatico'), default='manual',
                        help='Manual: secuencia escrita; automático: estrategia por condiciones')
    parser.add_argument('--rutinas', nargs='+', help='Nombres de rutinas en orden (solo manual)')
    args = parser.parse_args()
    if args.modo == 'automatico' and args.rutinas is not None:
        parser.error('--rutinas solo se usa en modo manual')
    if not args.dry_run and not args.port:
        parser.error('Con robot físico debes indicar --port COMxx (o usar --dry-run)')
    try:
        ejecutar(args)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('\nCtrl+C: parada solicitada.')
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
