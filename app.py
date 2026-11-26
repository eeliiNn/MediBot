from collections import deque
from xml.sax.saxutils import escape

from flask import Flask, Response, jsonify, render_template, request  # type: ignore[import-not-found]

import config
import database as db
import formato as F
import mensajeria
import recordatorios
import reloj
from chatbot import procesar_mensaje

app = Flask(__name__)
db.init_db()


def atender(telefono, texto):
    """Procesa un mensaje y guarda la conversación."""
    db.guardar_mensaje(telefono, "usuario", texto)
    respuesta = procesar_mensaje(telefono, texto)
    db.guardar_mensaje(telefono, "bot", respuesta)
    return respuesta


# ------------------------------------------------------------------ WhatsApp (Twilio)
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    texto = request.form.get("Body", "").strip()
    origen = request.form.get("From", "")
    respuesta = atender(origen, texto)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(respuesta)}</Message></Response>'
    return Response(xml, mimetype="application/xml")


@app.route("/", methods=["GET", "POST"])
def inicio():
    if request.method == "POST":                     # la guía configura Twilio apuntando a la raíz "/"
        return whatsapp_webhook()
    return render_template("index.html", modo=config.MODO, bot=config.NOMBRE_BOT)


# ------------------------------------------------------------------ WhatsApp (Vonage)
_vistos = deque(maxlen=500)


@app.post("/vonage/inbound")
def vonage_entrada():
    msg = mensajeria.extraer_mensaje_vonage(request.get_json(force=True, silent=True) or {})
    if msg:
        numero, texto, msg_id, _tipo = msg
        if not (msg_id and msg_id in _vistos):
            if msg_id:
                _vistos.append(msg_id)
            telefono = "+" + mensajeria.solo_digitos(numero)
            respuesta = (atender(telefono, texto) if texto else
                         "Por ahora solo entiendo mensajes de texto 🙂 Escribe *menu* para ver las opciones.")
            if config.vonage_listo():
                if not mensajeria.enviar_texto(telefono, respuesta):
                    print("[vonage] No se pudo enviar la respuesta (mira el error de arriba)")
            else:
                print(f"[vonage] MODO={config.MODO}: llegó un mensaje pero no hay credenciales para responder")
    return Response("", status=200)             


@app.post("/vonage/status")
def vonage_estado():
    """Estados de entrega (URL 'Status' del sandbox). No hace falta procesarlos."""
    return Response("", status=200)


# ------------------------------------------------------------------ API del simulador
@app.post("/api/mensaje")
def api_mensaje():
    datos = request.get_json(force=True, silent=True) or {}
    telefono = (datos.get("telefono") or "").strip()
    texto = (datos.get("texto") or "").strip()
    if not telefono or not texto:
        return jsonify(error="Faltan datos"), 400
    return jsonify(respuesta=atender(telefono, texto))


@app.get("/api/historial")
def api_historial():
    return jsonify(db.historial(request.args.get("telefono", "")))


@app.get("/api/notificaciones")
def api_notificaciones():
    telefono = request.args.get("telefono", "")
    pendientes = db.tomar_notificaciones(telefono)
    for n in pendientes:
        db.guardar_mensaje(telefono, "bot", n["mensaje"])
    return jsonify([n["mensaje"] for n in pendientes])


@app.get("/api/dev/hora")
def api_hora():
    a = reloj.ahora()
    texto = f"{F.DIAS[a.weekday()][:3].capitalize()} {a.day} {F.MESES[a.month - 1][:3]} · {F.hora12(a.strftime('%H:%M'))}"
    return jsonify(ahora=texto, desfase=reloj.desfase_minutos())


@app.post("/api/dev/avanzar")
def api_avanzar():
    minutos = int((request.get_json(force=True, silent=True) or {}).get("minutos", 0))
    recordatorios.avanzar_tiempo(max(0, min(minutos, 60 * 24 * 7)))
    return api_hora()


@app.post("/api/dev/borrar")
def api_borrar():
    telefono = ((request.get_json(force=True, silent=True) or {}).get("telefono") or "").strip()
    if telefono:
        db.borrar_datos(telefono)
    reloj.reiniciar()
    return jsonify(ok=True)


if __name__ == "__main__":
    recordatorios.iniciar_scheduler()
    print(f"\n  {config.NOMBRE_BOT} en modo '{config.MODO}'  ->  http://localhost:{config.PUERTO}\n")
    app.run(host="0.0.0.0", port=config.PUERTO, debug=False)
