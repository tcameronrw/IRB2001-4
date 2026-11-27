def decidir(cancha, rutina_actual, ultima_completada):
    """Llamada cada frame armado. Devuelve un nombre de RUTINAS o None.

    rutina_actual: rutina en ejecución (o None).
    ultima_completada: última rutina completada desde el armado.
    Si devuelves un nombre distinto, se interrumpe y reinicia el movimiento.
    Si devuelves None, el robot espera sin movimiento.
    Si devuelves la última rutina completada, espera sin repetirla.
    Para volver a ejecutarla, pasa antes por None u otra rutina.
    """
    # TODO: añadir condicionales de estrategia, por ejemplo:
    # if ...:  # amenaza al arco propio
    #     return "defender_arco"
    # elif ...:  # oportunidad de ataque
    #     return "empujar_arco"
    # elif ...:  # continuar una maniobra iniciada
    #     return rutina_actual
    return None
