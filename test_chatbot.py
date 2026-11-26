"""Pruebas automáticas de MediBot.  Uso:  python test_chatbot.py
Usan una base de datos temporal, no tocan tus datos reales."""
import os
import tempfile
from datetime import datetime

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["MODO"] = "local"

import database as db
import recordatorios as rec
import reloj
from chatbot import procesar_mensaje as bot

db.init_db()
TEL = "+50370000000"
fallos = 0


def dice(texto, *esperados, no=()):
    """Envía un mensaje y verifica que la respuesta contenga todo lo esperado."""
    global fallos
    r = bot(TEL, texto)
    ok = all(e.lower() in r.lower() for e in esperados) and not any(x.lower() in r.lower() for x in no)
    print(("✅" if ok else "❌"), f"Tú: {texto!r}")
    if not ok:
        fallos += 1
        print("   esperaba:", esperados, "| respuesta:\n", r)
    return r


def avisos():
    return [n["mensaje"] for n in db.tomar_notificaciones(TEL)]


def comprobar(cond, nombre):
    global fallos
    print(("✅" if cond else "❌"), nombre)
    fallos += 0 if cond else 1


# Lunes 5 de octubre de 2026, 07:30
reloj.fijar(datetime(2026, 10, 5, 7, 30))

print("\n--- Presentación ---")
dice("hola", "cómo te llamas")
dice("Me llamo ana maría", "Ana María", "1️⃣")
dice("menu", "Registrar medicamento")

print("\n--- Medicamento en una sola frase ---")
dice("Tomo paracetamol 500 mg cada 8 horas a las 8am por 5 días", "Paracetamol", "8:00 AM", "4:00 PM", "12:00 AM", "5 día")
dice("1", "Registré", "Paracetamol")

print("\n--- Medicamento paso a paso ---")
dice("1", "cómo se llama")
dice("Losartán", "dosis")
dice("50 mg", "hora")
dice("dos veces al día", "siempre")
dice("siempre", "Losartán", "8:00 AM", "8:00 PM", "continuo")
dice("2", "horario")
dice("7am y 9pm", "continuo", "7:00 AM", "9:00 PM")
dice("1", "Registré")
dice("mis medicamentos", "Paracetamol", "Losartán")

print("\n--- Cita ---")
dice("tengo cita mañana a las 3pm con el dentista", "Dentista", "martes 6 de octubre", "3:00 PM", "1 hora antes")
dice("1", "Cita agendada")
dice("quiero agendar una cita", "para qué es")
dice("Examen de laboratorio", "qué día")
dice("30/02", "no existe")
dice("el viernes", "qué hora")
dice("8", "Examen De Laboratorio", "8:00 AM")
dice("3", "cancelada")
dice("mis citas", "Dentista", "mañana")

print("\n--- Citas pasadas / conflictos ---")
dice("agendar cita con el pediatra hoy a las 6am", "ya pasó")
dice("menu", "Registrar")
dice("agendar cita dentista mañana a las 3pm", "misma hora")
dice("cancelar", "cancelé")

print("\n--- Recordatorios automáticos (viaje en el tiempo) ---")
rec.avanzar_tiempo(60)          # 08:00
a = avisos()
comprobar(any("Paracetamol" in x for x in a), "08:00 llega aviso de Paracetamol")
comprobar(not any("Losartán" in x for x in a), "Losartán (7am) no se avisa porque se creó después de esa hora hoy")
dice("posponer 20 minutos", "20 minutos")
rec.avanzar_tiempo(25)
comprobar(any("pospuesta" in x for x in avisos()), "Aviso de dosis pospuesta a los 20 min")
dice("ya me la tomé", "Registré", "Paracetamol", "Próxima toma")
dice("tomé", "ninguna dosis pendiente")

print("\n--- Aviso de cita 1 día antes (lunes 3pm -> martes 3pm) ---")
rec.avanzar_tiempo(7 * 60 + 5)   # ~15:30 lunes del 5
a = avisos()
comprobar(any("Dentista" in x and "mañana" in x.lower() for x in a), "Aviso de cita con 1 día de anticipación")
dice("agenda", "Tu agenda de hoy", "Paracetamol", "✅")

print("\n--- Aviso 1 hora antes y dosis omitida ---")
rec.avanzar_tiempo(23 * 60)      # martes 14:30 aprox
a = avisos()
comprobar(any("Dentista" in x and "hora" in x.lower() for x in a), "Aviso de cita 1 hora antes")
comprobar(any("Paracetamol" in x for x in a), "Dosis del martes avisadas")
rec.avanzar_tiempo(3 * 60)       # pasan 2h sin responder
dice("mi progreso", "Tu progreso", "omitidas", "Racha")

print("\n--- Eliminar ---")
dice("eliminar paracetamol", "Seguro")
dice("1", "Eliminé")
dice("borrar", "Qué quieres eliminar")
dice("2", "no tienes citas")

print("\n--- Errores de escritura y mensajes raros ---")
dice("quiero registrar un medicamneto", "cómo se llama")
dice("cancelar", "cancelé")
dice("asdfgh", "no entendí")
dice("gracias", "Con gusto")

print("\n" + ("🎉 Todas las pruebas pasaron" if fallos == 0 else f"⚠️ {fallos} prueba(s) fallaron"))
raise SystemExit(1 if fallos else 0)
