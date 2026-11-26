import re
from datetime import datetime, date, time, timedelta

import config
import database as db
import formato as F
from nlu import (Texto, norm, extraer_frecuencia, extraer_duracion, extraer_dosis, extraer_horas,
                 extraer_fecha, extraer_minutos, limpiar_nombre, detectar_intencion, es_si, es_no,
                 STOP_MED, STOP_CITA, STOP_PERSONA)
from reloj import ahora

HORAS_POR_DEFECTO = {1: ["08:00"], 2: ["08:00", "20:00"], 3: ["08:00", "14:00", "20:00"],
                     4: ["06:00", "12:00", "18:00", "22:00"]}
MENU_NUM = {"1": "registrar_medicamento", "2": "registrar_cita", "3": "ver_medicamentos",
            "4": "ver_citas", "5": "horarios", "6": "adherencia", "7": "eliminar", "8": "servicios"}
AYUDA_CORTA = "Escribe *menu* para ver las opciones."


def _menu(nombre, saludo=False):
    inicio = (f"¡Hola, {nombre}! 👋 Soy *{config.NOMBRE_BOT}* 🩺, tu asistente de medicamentos y citas. "
              if saludo else "")
    return (inicio + "¿Cómo puedo ayudarte?\n\n"
            "1️⃣ Registrar medicamento\n2️⃣ Agendar cita médica\n3️⃣ Mis medicamentos\n"
            "4️⃣ Mis citas\n5️⃣ Mi agenda de hoy\n6️⃣ Mi progreso\n7️⃣ Eliminar medicamento o cita\n"
            "8️⃣ Servicios y ayuda\n\n"
            "Escribe el número o cuéntame con tus palabras, por ejemplo:\n"
            "_Tomo losartán 50 mg cada 12 horas a las 8am_")


SERVICIOS = ("🩺 *Esto es lo que hace MediBot:*\n\n"
             "💊 *Medicamentos:* registra tu medicina, dosis y horarios, y te aviso a la hora exacta.\n"
             "📅 *Citas médicas:* agenda tu cita y te recuerdo 1 día antes y 1 hora antes.\n"
             "✅ *Confirmación:* cuando te avise, responde *tomé*, *posponer* u *omitir*.\n"
             "🗓️ *Mi agenda:* mira lo que te toca hoy.\n"
             "📊 *Mi progreso:* porcentaje de cumplimiento y racha de días.\n\n"
             "Puedes escribirme en lenguaje natural:\n"
             "• _Registrar ibuprofeno 400 mg 3 veces al día por 5 días_\n"
             "• _Tengo cita con el dentista el viernes a las 3pm_\n"
             "• _Posponer 20 minutos_\n\n" + AYUDA_CORTA)



def procesar_mensaje(telefono, texto):
    texto = (texto or "").strip()
    if not texto:
        return "Escríbeme un mensaje para poder ayudarte 🙂"

    usuario = db.get_usuario(telefono)
    if usuario is None:                                  
        db.crear_usuario(telefono)
        db.set_sesion(telefono, "ONB_NOMBRE")
        return (f"¡Hola! 👋 Soy *{config.NOMBRE_BOT}* 🩺, tu asistente de medicamentos y citas médicas. "
                "Te ayudo a no olvidar ninguna dosis ni consulta.\n\nAntes de empezar, ¿cómo te llamas?")

    estado, datos = db.get_sesion(telefono)
    n = norm(texto)
    tokens = set(re.findall(r"[a-z0-9]+", n))
    nombre = usuario["nombre"] or "amigo"

    if estado == "ONB_NOMBRE":
        return _onboarding(telefono, texto, n)

    if len(tokens) <= 3 and tokens & {"menu", "inicio"}:
        db.limpiar_sesion(telefono)
        return _menu(nombre)
    if estado and len(tokens) <= 3 and tokens & {"cancelar", "cancela", "salir"}:
        db.limpiar_sesion(telefono)
        return "Listo, cancelé lo que estábamos haciendo ✅\n\n" + AYUDA_CORTA

    intencion, puntaje = detectar_intencion(texto)
    pendientes = db.tomas_pendientes(telefono)

    # --- respuestas a un recordatorio ("tomé", "posponer", "omitir")
    if pendientes and intencion in ("tomada", "posponer", "omitida") and (not estado or puntaje >= 2):
        return _responder_toma(telefono, intencion, n, texto, nombre, pendientes)

    # --- conversaciones en curso
    if estado:
        return _continuar(telefono, estado, datos, texto, n, nombre)

    if n.strip(" .!") in MENU_NUM:
        intencion = MENU_NUM[n.strip(" .!")]
    elif intencion is None and pendientes and es_si(n):
        intencion = "tomada"
    elif intencion is None and pendientes and es_no(n):
        intencion = "posponer"

    if intencion == "saludo":
        return _menu(nombre, saludo=True)
    if intencion == "menu":
        return _menu(nombre)
    if intencion == "servicios":
        return SERVICIOS
    if intencion == "horarios":
        return _agenda(telefono)
    if intencion == "registrar_medicamento":
        return _avanzar_med(telefono, texto, {}, inicial=True)
    if intencion == "registrar_cita":
        return _avanzar_cita(telefono, texto, {}, inicial=True)
    if intencion == "ver_medicamentos":
        return _ver_medicamentos(telefono)
    if intencion == "ver_citas":
        return _ver_citas(telefono)
    if intencion in ("tomada", "posponer", "omitida"):
        return ("No tengo ninguna dosis pendiente por confirmar 🙂\n" + _proxima_toma_texto(telefono)
                + "\n\n" + AYUDA_CORTA)
    if intencion == "eliminar":
        return _iniciar_eliminar(telefono, n)
    if intencion == "adherencia":
        return _reporte(telefono)
    if intencion == "nombre":
        return _cambiar_nombre(telefono, texto)
    if intencion == "despedida":
        return ("¡Con gusto! 😊 Si tienes otra consulta, escríbeme cuando quieras. "
                "Cuídate mucho y recuerda tus medicinas. ¡Hasta luego!")
    return ("Lo siento, no entendí lo que dijiste 😅 ¿Podrías ser más específico?\n\n"
            "Por ejemplo: _registrar paracetamol 500 mg cada 8 horas_ o _agendar cita con el dentista_.\n"
            + AYUDA_CORTA)


def _onboarding(telefono, texto, n):
    if es_no(n) or n.strip() in ("omitir", "saltar"):
        nombre = "amigo"
    else:
        nombre = limpiar_nombre(texto, STOP_PERSONA, max_palabras=3)
        if not nombre:
            return "No logré entender tu nombre 😅 ¿Cómo te llamas? (o escribe *omitir*)"
    db.actualizar_nombre(telefono, nombre)
    db.limpiar_sesion(telefono)
    return f"¡Mucho gusto, {nombre}! 😊\n\n" + _menu(nombre)


def _cambiar_nombre(telefono, texto):
    nombre = limpiar_nombre(texto, STOP_PERSONA | {"cambiar", "cambia", "quiero", "que", "digas"}, 3)
    if not nombre:
        return "¿Cómo quieres que te llame? Escribe, por ejemplo: _Me llamo Ana_"
    db.actualizar_nombre(telefono, nombre)
    return f"¡Listo! Desde ahora te llamaré *{nombre}* 😊"


def _continuar(telefono, estado, datos, texto, n, nombre):
    if estado == "MED_SLOTS":
        return _avanzar_med(telefono, texto, datos)
    if estado == "MED_CONFIRMAR":
        return _confirmar_med(telefono, datos, n)
    if estado == "CITA_SLOTS":
        return _avanzar_cita(telefono, texto, datos)
    if estado == "CITA_CONFIRMAR":
        return _confirmar_cita(telefono, datos, n)
    if estado == "ELIM_TIPO":
        return _elegir_tipo_eliminar(telefono, n)
    if estado == "ELIM_ELEGIR":
        return _elegir_a_eliminar(telefono, datos, n)
    if estado == "ELIM_CONFIRMAR":
        return _confirmar_eliminar(telefono, datos, n)
    db.limpiar_sesion(telefono)
    return _menu(nombre)


def _resolver_horario(d):
    horas = d.get("horas_usuario") or []
    d.pop("horas", None)
    d.pop("horas_auto", None)
    if d.get("intervalo"):
        inicio = d.get("hora_inicio") or (horas[0] if horas else None)
        if inicio:
            h, m = (int(x) for x in inicio.split(":"))
            pasos = max(1, 24 // d["intervalo"])
            d["horas"] = sorted({f"{(h + k * d['intervalo']) % 24:02d}:{m:02d}" for k in range(pasos)})
    elif horas:
        d["horas"] = horas
    elif d.get("veces") in HORAS_POR_DEFECTO:
        d["horas"] = HORAS_POR_DEFECTO[d["veces"]]
        d["horas_auto"] = True


def _foco_med(d):
    if not d.get("nombre"):
        return "nombre"
    if not d.get("dosis"):
        return "dosis"
    _resolver_horario(d)
    if not d.get("horas"):
        return "hora_inicio" if d.get("intervalo") else "horario"
    if "dias" not in d:
        return "duracion"
    return None


PREGUNTAS_MED = {
    "nombre": "💊 ¿Cómo se llama el medicamento?",
    "dosis": "📏 ¿Qué dosis debes tomar? (ej. _500 mg_, _1 tableta_, _5 ml_). Si no la sabes escribe *omitir*.",
    "horario": ("⏰ ¿A qué hora(s) lo tomas? Dime las horas (_8:00 am, 2:00 pm y 8:00 pm_) "
                "o la frecuencia (_cada 8 horas_, _3 veces al día_)."),
    "duracion": "📆 ¿Por cuántos días lo tomarás? (ej. _7 días_, _2 semanas_). Si es de uso continuo escribe *siempre*.",
}


def _pregunta_med(foco, d):
    if foco == "hora_inicio":
        return (f"⏰ Lo tomarás *cada {d['intervalo']} horas*. ¿A qué hora será la primera dosis? "
                "(ej. _8:00 am_)")
    return PREGUNTAS_MED[foco]


def _avanzar_med(telefono, texto, d, inicial=False):
    foco_previo = d.get("foco")
    t = Texto(texto)
    frec = extraer_frecuencia(t)
    dur = extraer_duracion(t)
    dosis = extraer_dosis(t)
    horas = extraer_horas(t, solo_numero=foco_previo in ("horario", "hora_inicio"))
    resto = t.resto
    n = norm(texto)

    if frec:
        d.update(frec)
        d.pop("veces" if "intervalo" in frec else "intervalo", None)
    if horas:
        d["horas_usuario"] = horas
        if len(horas) > 1:                       # lista explícita de horas manda sobre la frecuencia
            d.pop("intervalo", None)
            d.pop("veces", None)
        elif foco_previo == "hora_inicio":
            d["hora_inicio"] = horas[0]
    if dur is not None:
        d["dias"] = dur
    elif foco_previo == "duracion":
        if re.fullmatch(r"\s*\d{1,3}\s*", n):
            d["dias"] = int(n)
        elif es_no(n) or "no se" in n:
            d["dias"] = 0
    if dosis:
        d["dosis"] = dosis
    elif foco_previo == "dosis":
        if es_no(n) or n.strip() in ("omitir", "no se", "ninguna", "-"):
            d["dosis"] = "Sin especificar"
        elif len(texto) <= 30:
            d["dosis"] = texto.strip()

    nombre_med = limpiar_nombre(resto, STOP_MED)
    if nombre_med and (foco_previo == "nombre" or (inicial and not d.get("nombre"))):
        d["nombre"] = nombre_med

    foco = _foco_med(d)
    if foco is None:
        d.pop("foco", None)
        db.set_sesion(telefono, "MED_CONFIRMAR", d)
        return _resumen_med(d)

    d["foco"] = foco
    db.set_sesion(telefono, "MED_SLOTS", d)
    if inicial:
        return "¡Perfecto! Vamos a registrar tu medicamento 💊\n\n" + _pregunta_med(foco, d)
    if foco == foco_previo:
        return "No logré entenderte 😅\n" + _pregunta_med(foco, d)
    return _pregunta_med(foco, d)


def _texto_duracion(d, hoy=None):
    hoy = hoy or ahora().date()
    if d.get("dias"):
        fin = hoy + timedelta(days=d["dias"] - 1)
        return f"{d['dias']} día(s), hasta el {F.fecha_larga(fin)}"
    return "Uso continuo (sin fecha de fin)"


def _resumen_med(d):
    auto = "\n_(Usé horarios sugeridos; puedes cambiarlos con la opción 2.)_" if d.get("horas_auto") else ""
    return ("📋 *Revisa tu medicamento:*\n\n"
            f"💊 *{d['nombre']}*\n📏 Dosis: {d['dosis']}\n⏰ Horarios: {F.lista_horas(d['horas'])}\n"
            f"📆 Duración: {_texto_duracion(d)}{auto}\n\n"
            "1️⃣ Confirmar\n2️⃣ Cambiar horario\n3️⃣ Cancelar")


def _confirmar_med(telefono, d, n):
    tk = set(re.findall(r"[a-z0-9]+", n))
    if n.strip() == "1" or es_si(n):
        hoy = ahora().date()
        fin = (hoy + timedelta(days=d["dias"] - 1)).isoformat() if d.get("dias") else None
        db.agregar_medicamento(telefono, d["nombre"], d["dosis"], d["horas"], hoy.isoformat(), fin)
        db.limpiar_sesion(telefono)
        return (f"✅ *¡Listo!* Registré *{d['nombre']}* ({d['dosis']}).\n"
                f"⏰ Te lo recordaré a las: {F.lista_horas(d['horas'])}\n"
                f"📆 {_texto_duracion(d, hoy)}\n\n" + _proxima_toma_texto(telefono) + "\n\n"
                "Cuando te avise, responde *tomé*, *posponer* u *omitir*.\n" + AYUDA_CORTA)
    if n.strip() == "2" or tk & {"cambiar", "editar", "horario", "horarios", "hora"}:
        for k in ("horas", "horas_usuario", "intervalo", "veces", "hora_inicio", "horas_auto"):
            d.pop(k, None)
        d["foco"] = "horario"
        db.set_sesion(telefono, "MED_SLOTS", d)
        return "Claro, cambiemos el horario ✏️\n\n" + PREGUNTAS_MED["horario"]
    if n.strip() == "3" or es_no(n):
        db.limpiar_sesion(telefono)
        return "Registro cancelado ❌ No guardé nada.\n" + AYUDA_CORTA
    return "Responde *1* para confirmar, *2* para cambiar el horario o *3* para cancelar."

def _foco_cita(d):
    if not d.get("motivo"):
        return "motivo"
    if not d.get("fecha"):
        return "fecha"
    if not d.get("hora"):
        return "hora"
    return None


PREGUNTAS_CITA = {
    "motivo": "🩺 ¿Para qué es la cita? Dime el médico o la especialidad (ej. _Dentista_, _Cardiología_, _Examen de laboratorio_).",
    "fecha": "📅 ¿Para qué día es? (ej. _mañana_, _el viernes_, _24 de octubre_, _24/10_)",
    "hora": "🕒 ¿A qué hora es la cita? (ej. _3:00 pm_, _10 am_)",
}


def _avanzar_cita(telefono, texto, d, inicial=False):
    foco_previo = d.get("foco")
    ahora_ = ahora()
    hoy = ahora_.date()
    t = Texto(texto)
    horas = extraer_horas(t, solo_numero=foco_previo == "hora")
    fecha = extraer_fecha(t, hoy)
    resto = t.resto
    aviso = ""

    if fecha == "invalida":
        aviso = "Esa fecha no existe o ya pasó 🤔 Intenta con otra.\n"
    elif fecha:
        d["fecha"] = fecha.isoformat()
    if horas:
        d["hora"] = horas[0]

    motivo = limpiar_nombre(resto, STOP_CITA)
    if motivo and (foco_previo == "motivo" or (inicial and not d.get("motivo"))):
        d["motivo"] = motivo

    if d.get("fecha") and d.get("hora"):
        dt = datetime.combine(date.fromisoformat(d["fecha"]), time.fromisoformat(d["hora"]))
        if date.fromisoformat(d["fecha"]) < hoy:
            d.pop("fecha")
            aviso = "Esa fecha ya pasó 🤔 Dime otra fecha.\n"
        elif dt <= ahora_:
            d.pop("hora")
            aviso = "Esa hora ya pasó el día de hoy 🤔 Dime otra hora.\n"
        elif db.cita_en(telefono, dt):
            d.pop("hora")
            aviso = "Ya tienes otra cita a esa misma hora 🤔 Dime otra hora.\n"

    foco = _foco_cita(d)
    if foco is None:
        d.pop("foco", None)
        db.set_sesion(telefono, "CITA_CONFIRMAR", d)
        return _resumen_cita(d, ahora_)

    d["foco"] = foco
    db.set_sesion(telefono, "CITA_SLOTS", d)
    if inicial:
        return "¡Claro! Vamos a agendar tu cita 📅\n\n" + aviso + PREGUNTAS_CITA[foco]
    if aviso:
        return aviso + PREGUNTAS_CITA[foco]
    if foco == foco_previo:
        return "No logré entenderte 😅\n" + PREGUNTAS_CITA[foco]
    return PREGUNTAS_CITA[foco]


def _dt_cita(d):
    return datetime.combine(date.fromisoformat(d["fecha"]), time.fromisoformat(d["hora"]))


def _avisos_cita(dt, ahora_, creado=None):
    """Lista legible de los avisos que sí se enviarán (los que aún no pasaron)."""
    creado = creado or ahora_
    etiquetas = {1440: "1 día antes", 60: "1 hora antes"}
    return [etiquetas.get(m, f"{m} min antes") for m in config.RECORDAR_CITA_MIN
            if dt - timedelta(minutes=m) >= creado]


def _resumen_cita(d, ahora_):
    dt = _dt_cita(d)
    avisos = _avisos_cita(dt, ahora_)
    linea = ("📲 Te recordaré: " + " y ".join(avisos)) if avisos else "📲 Te avisaré cuando se acerque la hora"
    return ("📋 *Revisa tu cita:*\n\n"
            f"🩺 *{d['motivo']}*\n📅 {F.fecha_larga(dt.date())}\n🕒 {F.hora12(d['hora'])}\n{linea}\n\n"
            "1️⃣ Confirmar\n2️⃣ Cambiar fecha u hora\n3️⃣ Cancelar")


def _confirmar_cita(telefono, d, n):
    tk = set(re.findall(r"[a-z0-9]+", n))
    if n.strip() == "1" or es_si(n):
        dt = _dt_cita(d)
        if dt <= ahora():
            d.pop("fecha", None); d.pop("hora", None); d["foco"] = "fecha"
            db.set_sesion(telefono, "CITA_SLOTS", d)
            return "Esa fecha y hora ya pasaron 🤔\n" + PREGUNTAS_CITA["fecha"]
        db.agregar_cita(telefono, d["motivo"], dt)
        db.limpiar_sesion(telefono)
        avisos = _avisos_cita(dt, ahora())
        extra = ("📲 Te recordaré " + " y ".join(avisos) + ".") if avisos else "📲 Te avisaré cuando se acerque."
        return (f"✅ *¡Cita agendada!*\n🩺 {d['motivo']}\n📅 {F.fecha_hora(dt)}\n{extra}\n\n" + AYUDA_CORTA)
    if n.strip() == "2" or tk & {"cambiar", "editar", "fecha", "hora"}:
        d.pop("fecha", None); d.pop("hora", None); d["foco"] = "fecha"
        db.set_sesion(telefono, "CITA_SLOTS", d)
        return "Claro, cambiemos la fecha ✏️\n\n" + PREGUNTAS_CITA["fecha"]
    if n.strip() == "3" or es_no(n):
        db.limpiar_sesion(telefono)
        return "Cita cancelada ❌ No guardé nada.\n" + AYUDA_CORTA
    return "Responde *1* para confirmar, *2* para cambiar fecha/hora o *3* para cancelar."


# ============================================================================ CONSULTAS
def _ver_medicamentos(telefono):
    meds = db.listar_medicamentos(telefono)
    if not meds:
        return "Todavía no tienes medicamentos registrados 💊\nEscribe *1* para registrar el primero."
    lineas = ["💊 *Tus medicamentos activos:*\n"]
    for i, m in enumerate(meds, 1):
        hasta = (f"hasta el {F.fecha_larga(date.fromisoformat(m['fecha_fin']))}"
                 if m["fecha_fin"] else "uso continuo")
        lineas.append(f"{i}. *{m['nombre']}* — {m['dosis']}\n    ⏰ {F.lista_horas(m['horas'])} · {hasta}")
    return "\n".join(lineas) + "\n\n" + _proxima_toma_texto(telefono)


def _ver_citas(telefono):
    citas = db.listar_citas(telefono)
    if not citas:
        return "No tienes citas programadas 📅\nEscribe *2* para agendar una."
    ahora_ = ahora()
    lineas = ["📅 *Tus próximas citas:*\n"]
    for i, c in enumerate(citas, 1):
        dt = db.a_dt(c["fecha_hora"])
        lineas.append(f"{i}. *{c['motivo']}* — {F.fecha_larga(dt.date())}, {F.hora12(dt.strftime('%H:%M'))} "
                      f"({F.relativo_dia(dt.date(), ahora_.date())})")
    return "\n".join(lineas)


def _proxima_toma(telefono):
    ahora_ = ahora()
    mejor = None
    for m in db.listar_medicamentos(telefono):
        creado = db.a_dt(m["creado"]) if m.get("creado") else ahora_
        for dia in range(0, 3):
            f = ahora_.date() + timedelta(days=dia)
            if date.fromisoformat(m["fecha_inicio"]) > f or (m["fecha_fin"] and date.fromisoformat(m["fecha_fin"]) < f):
                continue
            for h in m["horas"]:
                dt = datetime.combine(f, time.fromisoformat(h))
                if dt > ahora_ and dt >= creado and (mejor is None or dt < mejor[0]):
                    mejor = (dt, m)
    return mejor


def _proxima_toma_texto(telefono):
    p = _proxima_toma(telefono)
    if not p:
        return "No tienes próximas tomas programadas."
    dt, m = p
    return f"⏭️ Próxima toma: *{m['nombre']}* {F.cuando(dt, ahora())}."


def _agenda(telefono):
    ahora_ = ahora()
    hoy = ahora_.date()
    hoy_iso = hoy.isoformat()
    estados = db.tomas_del_dia(telefono, hoy_iso)
    iconos = {"tomada": "✅", "omitida": "❌", "enviado": "🔔", "pospuesta": "⏰"}
    eventos = []
    for m in db.listar_medicamentos(telefono):
        if date.fromisoformat(m["fecha_inicio"]) > hoy or (m["fecha_fin"] and date.fromisoformat(m["fecha_fin"]) < hoy):
            continue
        creado = db.a_dt(m["creado"])
        for h in m["horas"]:
            dt = datetime.combine(hoy, time.fromisoformat(h))
            if dt < creado:
                continue
            est = estados.get((m["id"], h))
            icono = iconos.get(est) or ("⏳" if dt > ahora_ else "▫️")
            eventos.append((dt, f"{icono} {F.hora12(h)} — 💊 {m['nombre']} ({m['dosis']})"))
    futuras = []
    for c in db.listar_citas(telefono):
        dt = db.a_dt(c["fecha_hora"])
        if dt.date() == hoy:
            eventos.append((dt, f"{'⏳' if dt > ahora_ else '▫️'} {F.hora12(dt.strftime('%H:%M'))} — 🩺 Cita: {c['motivo']}"))
        elif dt.date() > hoy and len(futuras) < 3:
            futuras.append(f"• {c['motivo']} — {F.fecha_larga(dt.date())}, {F.hora12(dt.strftime('%H:%M'))}")
    if not eventos and not futuras:
        return "No tienes nada programado todavía 🙂\nEscribe *1* para registrar un medicamento o *2* para agendar una cita."
    salida = [f"🗓️ *Tu agenda de hoy* ({F.fecha_larga(hoy)})\n"]
    salida += [txt for _, txt in sorted(eventos)] or ["Hoy no tienes tomas ni citas 🎉"]
    if futuras:
        salida += ["\n📅 *Próximas citas:*"] + futuras
    salida.append("\n" + _proxima_toma_texto(telefono))
    return "\n".join(salida)


# ============================================================================ RESPUESTA A RECORDATORIOS
def _responder_toma(telefono, intencion, n, texto, nombre, pendientes):
    elegidas = [p for p in pendientes if norm(p["nombre"]) in n] or pendientes
    nombres = ", ".join(f"*{p['nombre']}*" for p in elegidas)

    if intencion == "tomada":
        for p in elegidas:
            db.actualizar_toma(p["id"], "tomada")
        return (f"✅ ¡Muy bien, {nombre}! Registré tu toma de {nombres}.\n" + _proxima_toma_texto(telefono))

    if intencion == "omitida":
        for p in elegidas:
            db.actualizar_toma(p["id"], "omitida")
        return (f"Entendido, marqué {nombres} como *omitida* ❌. Intenta no saltarte dosis; "
                "si tienes dudas, consulta a tu médico.\n" + _proxima_toma_texto(telefono))

    minutos = extraer_minutos(texto) or config.POSPONER_MIN
    cuando = ahora() + timedelta(minutes=minutos)
    for p in elegidas:
        db.actualizar_toma(p["id"], "pospuesta", recordar_en=cuando)
    return f"⏰ Listo, te recordaré {nombres} de nuevo en *{minutos} minutos*."


# ============================================================================ ELIMINAR
def _iniciar_eliminar(telefono, n):
    meds = db.listar_medicamentos(telefono)
    citas = db.listar_citas(telefono)
    for m in meds:                                   # "eliminar paracetamol"
        if norm(m["nombre"]) in n:
            return _preguntar_eliminar(telefono, "med", m["id"], m["nombre"])
    for c in citas:
        if norm(c["motivo"]) in n:
            return _preguntar_eliminar(telefono, "cita", c["id"], c["motivo"])
    if "cita" in n or "citas" in n:
        return _listar_para_eliminar(telefono, "cita")
    if re.search(r"medic|pastilla|tratamiento|medicina", n):
        return _listar_para_eliminar(telefono, "med")
    db.set_sesion(telefono, "ELIM_TIPO")
    return "¿Qué quieres eliminar?\n\n1️⃣ Un medicamento\n2️⃣ Una cita\n\n(escribe *cancelar* para salir)"


def _elegir_tipo_eliminar(telefono, n):
    if n.strip() == "1" or re.search(r"medic|pastilla|tratamiento|medicina", n):
        return _listar_para_eliminar(telefono, "med")
    if n.strip() == "2" or "cita" in n:
        return _listar_para_eliminar(telefono, "cita")
    return "Responde *1* para medicamento o *2* para cita (o *cancelar* para salir)."


def _listar_para_eliminar(telefono, tipo):
    if tipo == "med":
        items = [(m["id"], f"*{m['nombre']}* — {m['dosis']}") for m in db.listar_medicamentos(telefono)]
        vacio = "No tienes medicamentos registrados."
    else:
        items = []
        for c in db.listar_citas(telefono):
            dt = db.a_dt(c["fecha_hora"])
            items.append((c["id"], f"*{c['motivo']}* — {F.fecha_larga(dt.date())}, {F.hora12(dt.strftime('%H:%M'))}"))
        vacio = "No tienes citas programadas."
    if not items:
        db.limpiar_sesion(telefono)
        return vacio + "\n" + AYUDA_CORTA
    db.set_sesion(telefono, "ELIM_ELEGIR",
                  {"tipo": tipo, "items": [(i, t.replace("*", "")) for i, t in items]})
    lista = "\n".join(f"{k}. {t}" for k, (_, t) in enumerate(items, 1))
    return f"¿Cuál quieres eliminar? Escribe el número:\n\n{lista}\n\n(escribe *cancelar* para salir)"


def _elegir_a_eliminar(telefono, d, n):
    items = d["items"]
    elegido = None
    if n.strip().isdigit() and 1 <= int(n.strip()) <= len(items):
        elegido = items[int(n.strip()) - 1]
    else:
        for item in items:
            if norm(item[1].split(" — ")[0]) in n:
                elegido = item
    if not elegido:
        return f"Escribe un número del 1 al {len(items)} (o *cancelar* para salir)."
    return _preguntar_eliminar(telefono, d["tipo"], elegido[0], elegido[1].split(" — ")[0])


def _preguntar_eliminar(telefono, tipo, item_id, titulo):
    db.set_sesion(telefono, "ELIM_CONFIRMAR", {"tipo": tipo, "id": item_id, "titulo": titulo})
    return f"¿Seguro que quieres eliminar *{titulo}*?\n\n1️⃣ Sí, eliminar\n2️⃣ No, conservar"


def _confirmar_eliminar(telefono, d, n):
    if n.strip() == "1" or es_si(n):
        if d["tipo"] == "med":
            db.desactivar_medicamento(d["id"])
        else:
            db.cambiar_estado_cita(d["id"], "cancelada")
        db.limpiar_sesion(telefono)
        return f"🗑️ Eliminé *{d['titulo']}*. Ya no recibirás recordatorios de eso.\n" + AYUDA_CORTA
    if n.strip() == "2" or es_no(n):
        db.limpiar_sesion(telefono)
        return "Perfecto, no eliminé nada 👍\n" + AYUDA_CORTA
    return "Responde *1* para eliminar o *2* para conservar."


# ============================================================================ PROGRESO
def _reporte(telefono):
    filas = [f for f in db.tomas_usuario(telefono) if f["estado"] in ("tomada", "omitida")]
    if not filas:
        return ("📊 Aún no tengo tomas registradas para calcular tu progreso.\n"
                "Cuando confirmes tus dosis con *tomé*, aquí verás tu cumplimiento.")
    hoy = ahora().date()

    def pct(lista):
        return round(100 * sum(1 for f in lista if f["estado"] == "tomada") / len(lista)) if lista else 0

    semana = [f for f in filas if date.fromisoformat(f["fecha"]) > hoy - timedelta(days=7)]
    por_med = {}
    for f in filas:
        por_med.setdefault(f["nombre"], []).append(f)

    racha = 0
    dia = hoy
    while True:
        del_dia = [f for f in filas if f["fecha"] == dia.isoformat()]
        if not del_dia:
            if dia == hoy:
                dia -= timedelta(days=1)
                continue
            break
        if any(f["estado"] == "omitida" for f in del_dia):
            break
        racha += 1
        dia -= timedelta(days=1)

    lineas = ["📊 *Tu progreso*\n",
              f"Total: {F.barra(pct(filas))}",
              f"Últimos 7 días: {F.barra(pct(semana))}"]
    if len(por_med) > 1:
        lineas.append("\n*Por medicamento:*")
        lineas += [f"• {nom}: {pct(lst)}%" for nom, lst in por_med.items()]
    tomadas = sum(1 for f in filas if f["estado"] == "tomada")
    lineas.append(f"\n✅ Tomadas: {tomadas} · ❌ Omitidas: {len(filas) - tomadas}")
    lineas.append(f"🔥 Racha: *{racha}* día(s) sin omitir dosis")
    lineas.append("\n" + ("¡Excelente constancia! 🌟" if pct(filas) >= 90 else
                          "Vas bien, ¡sigue así! 💪" if pct(filas) >= 70 else
                          "Intenta no saltarte dosis; los recordatorios están para ayudarte 🙂"))
    return "\n".join(lineas)
