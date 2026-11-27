# Datos de cada frame para las rutinas
from dataclasses import dataclass
from typing import Optional
from perception import Blob

Punto = tuple[float, float]


@dataclass
class EstadoCancha:
    estado_pid: Optional[tuple[float, float]]
    delantero: Optional[Blob]
    trasero: Optional[Blob]
    balon: Optional[Blob]
    frame: object
    # TODO E4: obtener coordenadas en la imagen original y configurar lado de juego.
    linea_central: Optional[tuple[Punto, Punto]] = None
    centro_cancha: Optional[Punto] = None
    arco_propio: Optional[Punto] = None
    arco_enemigo: Optional[Punto] = None

    @property
    def posicion_robot(self) -> Optional[Punto]:
        if self.delantero is None or self.trasero is None:
            return None
        f, r = self.delantero.centro, self.trasero.centro
        return ((f[0] + r[0]) / 2, (f[1] + r[1]) / 2)

    @property
    def posicion_balon(self) -> Optional[Punto]:
        return None if self.balon is None else self.balon.centro


def construir_estado(frame, blobs, colores, estado_pid):
    detectados = {c.nombre: b for c, b in zip(colores, blobs)}
    return EstadoCancha(estado_pid, detectados.get("DELANTE"),
                       detectados.get("ATRAS"), detectados.get("BALON"), frame)
