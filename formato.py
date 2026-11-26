"""formato.py - Funciones para mostrar fechas, horas y barras de progreso en español."""
from datetime import datetime, date, timedelta

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def hora12(hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def lista_horas(horas):
    return ", ".join(hora12(h) for h in horas)


def fecha_larga(d):
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def fecha_hora(dt):
    return f"{fecha_larga(dt.date())} a las {hora12(dt.strftime('%H:%M'))}"


def relativo_dia(d, hoy):
    delta = (d - hoy).days
    if delta == 0:
        return "hoy"
    if delta == 1:
        return "mañana"
    if delta > 1:
        return f"en {delta} días"
    return fecha_larga(d)


def cuando(dt, ahora):
    """Texto natural para un recordatorio de cita: 'en 1 hora', 'hoy a las…', 'mañana a las…'."""
    minutos = round((dt - ahora).total_seconds() / 60)
    if minutos <= 0:
        return "ahora"
    if minutos < 90:
        return f"en {minutos} minutos" if minutos != 60 else "en 1 hora"
    hora = hora12(dt.strftime("%H:%M"))
    delta = (dt.date() - ahora.date()).days
    if delta == 0:
        return f"hoy a las {hora}"
    if delta == 1:
        return f"mañana a las {hora}"
    return f"el {fecha_larga(dt.date())} a las {hora}"


def barra(porcentaje, largo=10):
    llenos = round(porcentaje / 100 * largo)
    return "▓" * llenos + "░" * (largo - llenos) + f" {porcentaje}%"
