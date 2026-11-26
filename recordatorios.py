"""recordatorios.py - Motor de recordatorios automáticos.

Un hilo en segundo plano llama a revisar() cada pocos segundos y decide qué avisar:
  * Dosis de medicamentos en sus horarios establecidos.
  * Dosis pospuestas ("posponer") cuando se cumple el tiempo.
  * Citas: 1 día antes y 1 hora antes (configurable en config.py).
  * Dosis sin respuesta -> se marcan como omitidas (alimenta el reporte de progreso).

Local  : el aviso se guarda en la tabla 'notificaciones' y el simulador web lo muestra.
Twilio : el aviso se envía por WhatsApp con client.messages.create().
"""
import threading
import time as _time
from datetime import datetime, date, time, timedelta

import config
import database as db
import formato as F
import mensajeria
from reloj import ahora

_candado = threading.Lock()
_hilo = None


# ----------------------------------------------------------------------- envío
def enviar(telefono, mensaje):
    """Envía por WhatsApp real (Vonage o Twilio); si no hay canal real o falla, queda para el simulador."""
    if mensajeria.canal_real() and mensajeria.enviar_texto(telefono, mensaje):
        db.guardar_mensaje(telefono, "bot", mensaje)
        return
    db.crear_notificacion(telefono, mensaje)


# ----------------------------------------------------------------------- revisiones
def _medicamentos(now):
    hoy = now.date()
    for med in db.medicamentos_activos():
        inicio = date.fromisoformat(med["fecha_inicio"])
        fin = date.fromisoformat(med["fecha_fin"]) if med["fecha_fin"] else None
        if fin and hoy > fin:
            db.desactivar_medicamento(med["id"])
            enviar(med["telefono"], f"🎉 ¡Terminaste tu tratamiento de *{med['nombre']}*! "
                                    "Ya no recibirás más recordatorios de este medicamento.")
            continue
        if hoy < inicio:
            continue
        creado = db.a_dt(med["creado"])
        for hora in med["horas"]:
            programada = datetime.combine(hoy, time.fromisoformat(hora))
            if now < programada or programada < creado:
                continue
            retraso = (now - programada).total_seconds() / 60
            if retraso <= config.VENTANA_RECORDATORIO_MIN:
                if db.registrar_toma(med["id"], hoy.isoformat(), hora, "enviado", now):
                    enviar(med["telefono"], _texto_toma(med["nombre"], med["dosis"], hora))
            else:
                db.registrar_toma(med["id"], hoy.isoformat(), hora, "perdida")


def _mayus(texto):
    return texto[:1].upper() + texto[1:]


def _texto_toma(nombre, dosis, hora, repetido=False):
    cab = "⏰ *Te recuerdo tu dosis pospuesta*" if repetido else "💊 *¡Hora de tu medicina!*"
    return (f"{cab}\n\n*{nombre}* — {dosis}\n🕒 Programada: {F.hora12(hora)}\n\n"
            "¿Ya la tomaste? Responde *tomé*, *posponer* u *omitir*.")


def _pospuestas(now):
    for t in db.tomas_pospuestas_vencidas(now):
        db.actualizar_toma(t["id"], "enviado", enviado_en=now)
        enviar(t["telefono"], _texto_toma(t["nombre"], t["dosis"], t["hora"], repetido=True))


def _sin_respuesta(now):
    limite = now - timedelta(minutes=config.OMITIR_TRAS_MIN)
    for t in db.tomas_sin_respuesta(limite):
        db.actualizar_toma(t["id"], "omitida")


def _citas(now):
    for c in db.citas_activas():
        fecha = db.a_dt(c["fecha_hora"])
        if now >= fecha + timedelta(hours=1):
            db.cambiar_estado_cita(c["id"], "pasada")
            continue
        if now >= fecha:
            continue
        creado = db.a_dt(c["creado"])
        vencidos = []
        for minutos in config.RECORDAR_CITA_MIN:
            disparo = fecha - timedelta(minutes=minutos)
            if disparo < creado or now < disparo or db.recordatorio_cita_enviado(c["id"], minutos):
                continue
            vencidos.append(minutos)
        if vencidos:
            for m in vencidos:                       # si se juntan varios, solo se envía el más cercano
                db.marcar_recordatorio_cita(c["id"], m)
            enviar(c["telefono"], f"📅 *Recordatorio de cita*\n\n🩺 {c['motivo']}\n"
                                  f"🕒 {_mayus(F.cuando(fecha, now))} ({F.fecha_hora(fecha)})")


def revisar(now=None):
    with _candado:
        now = now or ahora()
        _medicamentos(now)
        _pospuestas(now)
        _sin_respuesta(now)
        _citas(now)


# ----------------------------------------------------------------------- hilo
def iniciar_scheduler():
    global _hilo
    if _hilo and _hilo.is_alive():
        return

    def bucle():
        while True:
            try:
                revisar()
            except Exception as e:
                print(f"[recordatorios] error: {e}")
            _time.sleep(config.INTERVALO_SCHEDULER_SEG)

    _hilo = threading.Thread(target=bucle, daemon=True, name="recordatorios")
    _hilo.start()


def avanzar_tiempo(minutos, paso=5):
    """Adelanta el reloj en pasos pequeños, revisando en cada paso (para demostraciones)."""
    import reloj
    restante = minutos
    while restante > 0:
        avance = min(paso, restante)
        reloj.avanzar(avance)
        revisar()
        restante -= avance
