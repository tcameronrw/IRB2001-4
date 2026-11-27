import json
from pathlib import Path


def guardar_colores(ruta: Path, colores):
    datos = {c.nombre: c.rangos for c in colores}
    ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")



def cargar_colores(ruta: Path, colores):
    if not ruta.is_file():
        return False
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    for color in colores:
        if color.nombre not in datos:
            raise ValueError(f"Falta el color {color.nombre} en {ruta}")
        nuevos = datos[color.nombre]
        if set(nuevos) != {"H", "S", "V"}:
            raise ValueError(f"Datos HSV inválidos para {color.nombre}")
        for componente, techo in (("H", 179), ("S", 255), ("V", 255)):
            valores = nuevos[componente]
            if (not isinstance(valores, list) or len(valores) != 2
                    or any(type(v) is not int or not 0 <= v <= techo for v in valores)
                    or (componente != "H" and valores[0] > valores[1])):
                raise ValueError(f"Rango HSV inválido en {color.nombre}.{componente}")
        color.rangos = {k: list(v) for k, v in nuevos.items()}
    return True

