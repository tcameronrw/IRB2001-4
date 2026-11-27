from action import control, obtener_fase, ControladorSecuencial
from .tipos import Resultado, EN_CURSO, COMPLETADA, pendiente


def orientar_balon(cancha, dt, memoria):
    u, v = control(cancha.estado_pid, dt=dt)
    fase = obtener_fase()
    if fase != ControladorSecuencial.ORIENTAR:
        return Resultado(fase="DETENIDO", estado=COMPLETADA)
    return Resultado(0.0, v, fase, EN_CURSO)


def aproximar_balon(cancha, dt, memoria):
    u, v = control(cancha.estado_pid, dt=dt)
    fase = obtener_fase()
    estado = COMPLETADA if fase == ControladorSecuencial.DETENIDO else EN_CURSO
    return Resultado(u, v, fase, estado)


def ir_centro(cancha, dt, memoria):
    # TODO 2.5: identificar la línea central y definir el objetivo.
    # TODO: calcular error angular/distancia, controlar y detectar llegada.
    return pendiente("ir_centro")


def empujar_recto(cancha, dt, memoria):
    # TODO 2.7: partir alineado, conservar dirección y detectar final de cancha.
    return pendiente("empujar_recto")


def empujar_arco(cancha, dt, memoria):
    # TODO 2.8: posicionarse detrás del balón respecto al arco enemigo,
    # orientar, empujar y verificar llegada.
    return pendiente("empujar_arco")


def golpear_arco(cancha, dt, memoria):
    # TODO 2.9: preparar alineación, golpe y comprobar llegada del balón.
    return pendiente("golpear_arco")


# Bonus: se dejan igualmente sin implementar.
def ir_arco_propio(cancha, dt, memoria):
    # TODO: localizar y llegar al arco propio.
    return pendiente("ir_arco_propio")


def interponer_robot(cancha, dt, memoria):
    # TODO: posicionar robot entre balón y arco propio.
    return pendiente("interponer_robot")


def defender_arco(cancha, dt, memoria):
    # TODO: detectar amenaza y ejecutar una intercepción.
    return pendiente("defender_arco")


RUTINAS = {f.__name__: f for f in (
    orientar_balon, aproximar_balon, ir_centro, empujar_recto,
    empujar_arco, golpear_arco, ir_arco_propio, interponer_robot, defender_arco,
)}
