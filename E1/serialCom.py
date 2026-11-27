# =====================================================================
#  IRB2001 - Fundamentos a la Robótica - U4 Entrega 1
#  Emisor de velocidades por Bluetooth (PC -> robot)
# =====================================================================
#
#  Descripción general
#  -------------------
#  Programa interactivo: el usuario escribe dos velocidades enteras en
#  RPM (izquierda y derecha) y un hilo en segundo plano las envía al
#  robot por Bluetooth cada 0,3 s (INTERVALO_ENVIO_S). Las velocidades
#  se pueden cambiar en cualquier momento sin detener el envío.
#
#  Uso:
#    1. Emparejar el módulo Bluetooth del robot (ej. kit 1: IRB-G01, clave 0101).
#    2. Ajustar PUERTO al puerto COM del Bluetooth (ej. "COM20" en
#       Windows, "/dev/tty.IRB-Gxx" en macOS).
#    3. Ejecutar y escribir: <izquierda> <derecha>   ej:  50 -30
#       Para salir: "salir", "q", "exit" o Ctrl+C (envía velocidad 0,0).
#
#  ---------------------------------------------------------------------
#  FORMATO DE MENSAJES QUE SE ENVÍAN  (PC -> robot)
#  ---------------------------------------------------------------------
#  Paquete binario de 3 bytes:
#
#      [0xFF] [vel_izquierda + 100] [vel_derecha + 100]
#
#   - 0xFF: encabezado / inicio de trama.
#   - Velocidades enteras de -100 a +100 RPM, desplazadas en +100 para
#     que quepan en un byte (0..200). Negativo = retroceso.
#
#   Ejemplos:
#     izq =  100, der =  50   ->  FF C8 96
#     izq =   50, der = -30   ->  FF 96 46
#     izq =    0, der =   0   ->  FF 64 64   (detener)
#
#  ---------------------------------------------------------------------
#  FORMATO DE MENSAJES QUE SE RECIBEN  (robot -> PC)
#  ---------------------------------------------------------------------
#  Texto ASCII, una línea por mensaje, terminado en ';':
#
#   OK,<izq>,<der>;   El robot aceptó el paquete. <der> viene con el
#                     signo invertido (el motor derecho está en espejo).
#   ERR,VALOR;        El robot recibió un byte fuera de rango (> 200).
#   STOP,TIMEOUT;     El robot estuvo más de 1,5 s sin recibir comandos.
# =====================================================================

import threading
import time

import serial

# --- Configuración ---
PUERTO = "COM20"            # Puerto serial del módulo Bluetooth (cambiar según el PC)
BAUDIOS = 38400             # Debe coincidir con Serial3.begin(38400) del Arduino
RANGO_MIN, RANGO_MAX = -100, 100   # Rango permitido de velocidades [RPM]
ENCABEZADO = 0xFF           # Byte de inicio de trama
DESPLAZAMIENTO = 100        # Offset: byte enviado = RPM + 100
INTERVALO_ENVIO_S = 0.3     # Cada cuánto se reenvía la referencia [s] (< timeout de 1,5 s del robot)

# Valida las dos velocidades y arma el paquete binario
# [0xFF, izquierda + 100, derecha + 100].
# Lanza ValueError si alguna no es un entero entre -100 y 100.
def construir_paquete(izquierda: int, derecha: int) -> bytes:
    for nombre, velocidad in (("izquierda", izquierda), ("derecha", derecha)):
        if type(velocidad) is not int or not RANGO_MIN <= velocidad <= RANGO_MAX:
            raise ValueError(
                f"La velocidad {nombre} debe ser un entero de "
                f"{RANGO_MIN} a {RANGO_MAX} RPM."
            )
    return bytes([ENCABEZADO, izquierda + DESPLAZAMIENTO, derecha + DESPLAZAMIENTO])

# Hilo de envío: cada INTERVALO_ENVIO_S lee las referencias actuales
# (protegidas por el candado), envía el paquete al robot y lee su
# respuesta ("OK,...;", "ERR,VALOR;" o "STOP,TIMEOUT;").
# Solo imprime cuando cambian las velocidades o cuando llega un error/stop,
# para no llenar la consola. Termina cuando se activa el evento "detener".
def trabajador_bluetooth(conexion, referencias, candado, detener):
    ultimo_mostrado = None   # Última pareja (izq, der) informada en consola
    while not detener.is_set():
        # Copia de las referencias actuales (las modifica el hilo principal)
        with candado:
            izquierda, derecha = referencias[0], referencias[1]

        try:
            # Envío del paquete y lectura de la respuesta del robot
            paquete = construir_paquete(izquierda, derecha)
            conexion.write(paquete)
            conexion.flush()
            respuesta = conexion.readline().decode("ascii", errors="replace").strip()

            if (izquierda, derecha) != ultimo_mostrado:
                # Velocidades nuevas: se informa si el robot confirmó
                print("\nEnviado")
                if respuesta:
                    print(f"Recibido")
                else:
                    print("No recibido")
                ultimo_mostrado = (izquierda, derecha)
            elif respuesta.startswith("ERR") or respuesta.startswith("STOP"):
                # Mismas velocidades: solo se muestran errores o timeout
                print(f"\nRespuesta: {respuesta}")
        except (serial.SerialException, OSError, ValueError) as exc:
            # Falla de comunicación: se detiene todo el programa
            print(f"\nError durante envio: {exc}")
            detener.set()
            return

        # Espera hasta el próximo envío (o sale antes si se pide detener)
        detener.wait(INTERVALO_ENVIO_S)

# Programa principal: abre el puerto, lanza el hilo de envío y lee
# velocidades desde el teclado. Al salir, envía velocidad 0,0 al robot.
def main():
    try:
        with serial.Serial(PUERTO, BAUDIOS, timeout=0.2, write_timeout=0.5) as conexion:
            time.sleep(1.0)   # Espera a que se establezca la conexión
            print("Ingrese: vel_izq vel_der")

            # Estado compartido entre el hilo principal y el de envío
            referencias = [0, 0]             # [izquierda, derecha] en RPM
            candado = threading.Lock()       # Protege el acceso a "referencias"
            detener = threading.Event()      # Señal para terminar el hilo
            hilo = threading.Thread(
                target=trabajador_bluetooth,
                args=(conexion, referencias, candado, detener),
                daemon=True,
            )
            hilo.start()

            try:
                # Lectura de teclado: "<izquierda> <derecha>" o comando de salida
                while not detener.is_set():
                    entrada = input("Izquierda Derecha (RPM): ").strip().lower()
                    if entrada in ("salir", "q", "exit"):
                        break
                    partes = entrada.split()
                    if len(partes) != 2:
                        print("Ingresa dos numeros enteros")
                        continue
                    try:
                        # Convierte a enteros y valida el rango (sin enviar)
                        izquierda, derecha = map(int, partes)
                        construir_paquete(izquierda, derecha)
                    except ValueError as exc:
                        print(f"Entrada incorrecta: {exc}")
                        continue

                    # Actualiza las referencias; el hilo las enviará en el próximo ciclo
                    with candado:
                        referencias[0] = izquierda
                        referencias[1] = derecha
            except (KeyboardInterrupt, EOFError):
                print("\nFinalizando...")
            finally:
                # Detiene el hilo de envío y manda un último paquete de parada (0, 0)
                detener.set()
                hilo.join()
                try:
                    parada = construir_paquete(0, 0)
                    conexion.write(parada)
                    conexion.flush()
                    print(f"Stop solicitado: {parada.hex(' ').upper()}")
                except (serial.SerialException, OSError) as exc:
                    print(f"no se pudo enviar: {exc}")

    except (serial.SerialException, OSError) as exc:
        # No se pudo abrir el puerto (nombre incorrecto, Bluetooth no emparejado, etc.)
        print(f"No se pudo usar {PUERTO}: {exc}")


if __name__ == "__main__":
    main()
