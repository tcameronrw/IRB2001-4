from action import control
from . import automatico
from .manual import SECUENCIA_MANUAL
from .movimientos import RUTINAS
from .tipos import (Resultado, EN_CURSO, COMPLETADA, PENDIENTE, ESPERA, TRANSICION)


class GestorRutinas:
    def __init__(self, modo="manual", secuencia=None):
        if modo not in ("manual", "automatico"):
            raise ValueError(f"Modo desconocido: {modo}")
        self.modo = modo
        self.secuencia = tuple(SECUENCIA_MANUAL if secuencia is None else secuencia)
        if modo == "manual" and not self.secuencia:
            raise ValueError("La secuencia manual no puede estar vacía")
        if any(nombre not in RUTINAS for nombre in self.secuencia) and modo == "manual":
            raise ValueError("Nombre de rutina desconocido en secuencia manual")
        self.reiniciar()

    def reiniciar(self):
        control(None, reset=True)
        self.indice = 0
        self.actual = None
        self.ultima_completada = None
        self.memoria = {}

    def reiniciar_rutina_actual(self):
        """Reinicia PID y memoria local, conservando el paso de la secuencia."""
        control(None, reset=True)
        self.memoria = {}

    def _cambiar(self, nombre):
        control(None, reset=True)
        self.actual = nombre
        self.memoria = {}

    def actualizar(self, cancha, dt):
        if self.modo == "manual":
            if self.indice >= len(self.secuencia):
                return Resultado(fase="DETENIDO", estado=COMPLETADA)
            nombre = self.secuencia[self.indice]
        else:
            nombre = automatico.decidir(cancha, self.actual, self.ultima_completada)
            if nombre is None:
                if self.actual is not None:
                    self._cambiar(None)
                self.ultima_completada = None  # Permite repetir tras una espera.
                return Resultado(fase="AUTO: EN ESPERA", estado=ESPERA)
            if nombre not in RUTINAS:
                raise ValueError(f"Rutina automática desconocida: {nombre}")
            if nombre == self.ultima_completada and self.actual is None:
                return Resultado(fase="AUTO: EN ESPERA", estado=ESPERA)

        if nombre != self.actual:
            anterior = self.actual
            self._cambiar(nombre)
            if anterior is not None:
                return Resultado(fase="CAMBIO DE RUTINA", estado=TRANSICION)

        resultado = RUTINAS[nombre](cancha, dt, self.memoria)
        if resultado.estado == PENDIENTE:
            self._cambiar(None)
            return Resultado(fase=resultado.fase, estado=PENDIENTE)
        if resultado.estado == COMPLETADA:
            self.ultima_completada = nombre
            self._cambiar(None)
            if self.modo == "manual":
                self.indice += 1
                if self.indice == len(self.secuencia):
                    return Resultado(fase=resultado.fase, estado=COMPLETADA)
            return Resultado(fase=f"FIN: {nombre}", estado=TRANSICION)
        if resultado.estado == ESPERA:
            return Resultado(fase=resultado.fase, estado=ESPERA)
        if resultado.estado != EN_CURSO:
            raise ValueError(f"Estado de rutina inválido: {resultado.estado}")
        return resultado
