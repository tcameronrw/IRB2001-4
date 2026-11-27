"""Interfaz segura con el protocolo binario DE LA E1, sin cambiarlo.

PC -> Arduino: [0xFF, rpm_izq + 100, rpm_der + 100].
Arduino -> PC: OK,<rpm_motor1>,<rpm_motor2>; / ERR,VALOR; / STOP,TIMEOUT;
ATENCIÓN: el firmware invierte internamente el signo del motor DERECHO.
El computador envía RPM en convención de avance: ambas POSITIVAS = avanzar.
"""

import math
import time


def construir_paquete(izquierda: int, derecha: int) -> bytes:
    """Misma codificación de serialCom.py de E1."""
    if any(type(v) is not int or not -100 <= v <= 100 for v in (izquierda, derecha)):
        raise ValueError("Se requieren velocidades enteras de -100 a 100 RPM")
    return bytes((0xFF, izquierda + 100, derecha + 100))


def convertir_a_rpm(u: float, v: float, escala: float = 1.0,
                    max_rpm: float = 100.0) -> tuple[float, float]:
    """Salida Webots: izq = u + v; der = u - v (rad/s -> RPM).

    La inversión eléctrica de la rueda derecha la realiza Arduino, NO Python.
    """
    if not all(math.isfinite(float(x)) for x in (u, v, escala, max_rpm)):
        raise ValueError("Velocidades y límites deben ser números finitos")
    if escala <= 0 or max_rpm <= 0 or max_rpm > 100:
        raise ValueError("La escala y el límite de RPM deben ser positivos; max_rpm <= 100")
    conversion = (60.0 / (2.0 * math.pi)) * escala
    izq = max(-max_rpm, min(max_rpm, (u + v) * conversion))
    der = max(-max_rpm, min(max_rpm, (u - v) * conversion))
    return float(izq), float(der)


class LimitadorRampa:
    """Evita saltos abruptos de referencia; stop por seguridad salta la rampa."""
    def __init__(self, limite_rpm_por_segundo: float):
        if limite_rpm_por_segundo <= 0:
            raise ValueError("La pendiente de la rampa debe ser positiva")
        self.pendiente = limite_rpm_por_segundo
        self.referencia = (0.0, 0.0)

    def aplicar(self, velocidades: tuple[float, float], dt: float) -> tuple[int, int]:
        max_delta = self.pendiente * max(dt, 0.0)
        result = []
        for anterior, objetivo in zip(self.referencia, velocidades):
            result.append(anterior + max(-max_delta, min(max_delta, objetivo - anterior)))
        self.referencia = (result[0], result[1])
        return tuple(int(round(x)) for x in result)

    def detener(self) -> tuple[int, int]:
        self.referencia = (0.0, 0.0)
        return 0, 0


class BluetoothE1:
    def __init__(self, puerto: str, baudios: int = 38400, intervalo: float = 0.15):
        self.puerto = puerto
        self.baudios = baudios
        self.intervalo = intervalo
        self.puerto_serial = None
        self.ultima_orden = None
        self.ultimo_envio = 0.0
        self.ultimo_ack = None
        self._rx = bytearray()
        self.ultima_respuesta = ""
        self.error_reciente = None

    def __enter__(self):
        try:
            import serial  # pyserial se necesita solo con robot físico
        except ImportError as exc:
            raise RuntimeError("Falta pyserial. Ejecuta pip install -r requirements.txt") from exc
        self.puerto_serial = serial.Serial(
            self.puerto, baudrate=self.baudios, timeout=0, write_timeout=0.2
        )
        self.puerto_serial.reset_input_buffer()
        return self

    def enviar(self, izquierda: int, derecha: int, forzar: bool = False) -> None:
        orden = (int(izquierda), int(derecha))
        ahora = time.monotonic()
        if forzar or orden != self.ultima_orden or ahora - self.ultimo_envio >= self.intervalo:
            self.puerto_serial.write(construir_paquete(*orden))
            self.ultimo_envio = ahora
            self.ultima_orden = orden

    def leer_respuestas(self) -> list[str]:
        disponibles = self.puerto_serial.in_waiting
        if disponibles:
            self._rx.extend(self.puerto_serial.read(disponibles))
        if len(self._rx) > 4096:
            self._rx.clear()  # Evitar crecimiento indefinido por paquete corrupto
        respuestas = []
        while b"\n" in self._rx:
            indice = self._rx.index(b"\n")
            linea = bytes(self._rx[:indice]).decode("ascii", errors="replace").strip()
            del self._rx[:indice + 1]
            if not linea:
                continue
            respuestas.append(linea)
            self.ultima_respuesta = linea
            if linea.startswith("OK,") and linea.endswith(";"):
                self.ultimo_ack = time.monotonic()
            elif linea.startswith(("ERR", "STOP")):
                self.error_reciente = linea
        return respuestas

    def verificar_enlace(self, segundos: float = 2.0) -> bool:
        """Comprueba respuesta Arduino con velocidades CERO, antes de habilitar motores."""
        fin = time.monotonic() + segundos
        while time.monotonic() < fin:
            self.enviar(0, 0)
            self.leer_respuestas()
            if self.ultimo_ack is not None:
                return True
            time.sleep(0.04)
        return False

    def detener(self):
        self.enviar(0, 0, forzar=True)

    def __exit__(self, tipo, valor, traceback):
        if self.puerto_serial is not None:
            try:
                for _ in range(3):
                    self.detener()
                    time.sleep(0.02)
            except Exception:
                pass  # Si falló el enlace, Arduino E3 detiene por timeout.
            finally:
                self.puerto_serial.close()
                self.puerto_serial = None
