import math

from simple_pid import PID

from parameters import (
    DISTANCIA_SEGURA_PX, KP_GIRO, KI_GIRO, KD_GIRO,
    KP_AVANCE, KI_AVANCE, KD_AVANCE, MAX_GIRO, MAX_AVANCE,
    TOLERANCIA_ANGULO_GRADOS, FRAMES_ALINEADO,
    VELOCIDAD_GIRO_CASI_CERO, TOLERANCIA_DISTANCIA_PX,
    FRAMES_DETENIDO, VELOCIDAD_AVANCE_CASI_CERO
)


class ControladorSecuencial:
    ORIENTAR = "ORIENTACION"
    AVANZAR = "ACERCAMIENTO"
    DETENIDO = "DETENIDO"

    def __init__(self):
        # Un PID con error convencional: referencia - medición.
        # Invertimos la salida para convertir el signo a la convención
        # (u>0 = avance; v>0 = giro horario) del controlador base.
        self.pid_th = PID(
            KP_GIRO, KI_GIRO, KD_GIRO, setpoint=0.0,
            sample_time=None, output_limits=(-MAX_GIRO, MAX_GIRO),
        )
        self.pid_d = PID(
            KP_AVANCE, KI_AVANCE, KD_AVANCE,
            setpoint=DISTANCIA_SEGURA_PX,
            sample_time=None, output_limits=(-MAX_AVANCE, 0.0),
        )
        self.reset()

    def reset(self):
        self.pid_th.reset()
        self.pid_d.reset()
        self.fase = self.ORIENTAR
        self.frames_alineados = 0
        self.frames_detenidos = 0

    def actualizar(self, state, dt=None):
        if state is None:
            # Sin percepción no se ordena movimiento a ciegas.
            self.pid_th.reset()
            self.pid_d.reset()
            self.frames_alineados = 0
            self.frames_detenidos = 0
            return 0.0, 0.0

        distancia, theta = state
        if not (math.isfinite(distancia) and math.isfinite(theta)):
            self.pid_th.reset()
            self.pid_d.reset()
            self.frames_alineados = 0
            self.frames_detenidos = 0
            return 0.0, 0.0

        if self.fase == self.ORIENTAR:
            # theta positivo = balón a la derecha en la imagen.
            v = self.pid_th(theta, dt=dt)
            if (abs(theta) <= TOLERANCIA_ANGULO_GRADOS
                    and abs(v) <= VELOCIDAD_GIRO_CASI_CERO):
                self.frames_alineados += 1
            else:
                self.frames_alineados = 0

            if self.frames_alineados >= FRAMES_ALINEADO:
                self.fase = self.AVANZAR
                self.pid_d.reset()
                return 0.0, 0.0  # Se deteniene en cambio fases

            return 0.0, float(v)

        if self.fase == self.AVANZAR:
            # La orientación no se corrige durante el avance
            u = self.pid_d(distancia, dt=dt)
            if (distancia <= DISTANCIA_SEGURA_PX + TOLERANCIA_DISTANCIA_PX
                    and abs(u) <= VELOCIDAD_AVANCE_CASI_CERO):
                self.frames_detenidos += 1
            else:
                self.frames_detenidos = 0

            # Solo apagar para suprimir oscilación residual cuando ya hay
            # velocidad prácticamente nula durante varios ciclos seguidos.
            if self.frames_detenidos >= FRAMES_DETENIDO:
                self.fase = self.DETENIDO
                return 0.0, 0.0

            return float(u), 0.0

        return 0.0, 0.0


_controlador = ControladorSecuencial()


def control(state, reset=False, dt=None):
    if reset:
        _controlador.reset()
        return 0.0, 0.0
    return _controlador.actualizar(state, dt=dt)


def obtener_fase():
    return _controlador.fase
