from dataclasses import dataclass

EN_CURSO = "EN_CURSO"
COMPLETADA = "COMPLETADA"
PENDIENTE = "PENDIENTE"
ESPERA = "ESPERA"
TRANSICION = "TRANSICION"


@dataclass(frozen=True)
class Resultado:
    u: float = 0.0
    v: float = 0.0
    fase: str = "EN ESPERA"
    estado: str = ESPERA


def pendiente(nombre):
    return Resultado(fase=f"PENDIENTE: {nombre}", estado=PENDIENTE)
