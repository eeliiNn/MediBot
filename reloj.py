"""reloj.py - Reloj del sistema con desfase (sirve para probar recordatorios sin esperar).

Todo el proyecto usa ahora() en lugar de datetime.now(). En condiciones normales
el desfase es 0; en el modo demo se puede "adelantar el tiempo".
"""
from datetime import datetime, timedelta

_desfase = timedelta(0)


def ahora():
    return datetime.now().replace(microsecond=0) + _desfase


def avanzar(minutos):
    global _desfase
    _desfase += timedelta(minutes=minutos)


def fijar(momento):
    """Hace que ahora() devuelva 'momento' (y siga corriendo desde ahí). Útil en pruebas."""
    global _desfase
    _desfase = momento - datetime.now().replace(microsecond=0)


def reiniciar():
    global _desfase
    _desfase = timedelta(0)


def desfase_minutos():
    return int(_desfase.total_seconds() // 60)
