# IRB2001 — E4 modular

## Ejecutar

Desde esta carpeta, instala dependencias si faltan (`python -m pip install -r requirements.txt`). Usa el mismo entorno, cámara y puerto que funcionaban en E3. Primero prueba con `--dry-run`, que usa cámara pero no Bluetooth ni motores.

```bash
python robot_fisico.py --dry-run --camera 0
python robot_fisico.py --port COM20 --camera 0
python robot_fisico.py --dry-run --modo manual --rutinas orientar_balon
python robot_fisico.py --dry-run --modo manual --rutinas aproximar_balon
python robot_fisico.py --dry-run --modo manual --rutinas orientar_balon aproximar_balon
python robot_fisico.py --dry-run --modo automatico
```

Sustituye COM20/camera 0 si tu configuración difiere. ESPACIO arma o desarma, Q/ESC sale. Las teclas de HSV son las originales. Cada rearmado reinicia la secuencia desde el comienzo; no es una pausa con reanudación. El modo manual por defecto ejecuta `aproximar_balon`. Para evaluación individual, ejecuta una sola rutina por prueba. Una secuencia con varias rutinas avanza automáticamente después de que cada una se declare COMPLETADA, con un ciclo de orden cero entre ellas

## Qué editar

- `rutinas/manual.py`: escribe los nombres de los movimientos en `SECUENCIA_MANUAL`. `--rutinas` sustituye esa lista en una ejecución concreta.
- `rutinas/automatico.py`: añade los condicionales a `decidir`. Se evalúa en cada frame armado. Devuelve un nombre de rutina o `None` (espera sin movimiento). Si el nombre cambia durante la ejecución, se frena y reinicia la nueva rutina; al completar una rutina, no se repite hasta elegir otra o pasar por `None`. La estrategia inicial devuelve `None` siempre, así que no mueve el robot.
- `rutinas/movimientos.py`: implementa las rutinas pendientes. Las funciones `orientar_balon` y `aproximar_balon` reutilizan el PID original. Las otras devuelven PENDIENTE, orden cero y desarmado; no se saltan automáticamente.
- `cancha.py`: contiene el estado de un frame; los campos de línea central, centro y arcos están disponibles pero son `None` hasta implementar su detección o calibración. Completa `construir_estado` cuando definas esos elementos. `posicion_robot` es el punto medio de los marcadores (solo información nueva, no realimenta al PID original).

## Contrato de una rutina

```python
from .tipos import Resultado, EN_CURSO, COMPLETADA

# Ejemplo de estructura, no algoritmo implementado.
def nueva_rutina(cancha, dt, memoria):
    # TODO: evaluar condición de llegada con los datos de cancha.
    # Si termina: return Resultado(fase="DETENIDO", estado=COMPLETADA)
    # Si continúa: return Resultado(u, v, "FASE ACTUAL", EN_CURSO)
    from .tipos import pendiente
    return pendiente("nueva_rutina")
```

Cada llamada procesa un frame. `u,v` son las mismas variables de movimiento originales; la conversión a RPM se hace en `robot_fisico.py`. `dt` está en segundos y `memoria` es un diccionario que persiste mientras se ejecuta la rutina, reiniciado al cambiar o desarmar. No uses `while`, `sleep`, acceso directo a cámara ni escritura Bluetooth dentro de las rutinas. Añade las nuevas funciones a `RUTINAS`.

Importante: se mantiene la protección E3 que requiere los tres marcadores para armar y continuar cualquier movimiento. Incluso ir al centro exige que se vea el balón por ahora. Si después deseas que determinadas rutinas funcionen sin balón, modifica explícitamente esa protección con requisitos de percepción por rutina y compruébalo en laboratorio; no se modificó en esta versión. No se han recalibrado ni corregido convenciones de geometría o ganancias.