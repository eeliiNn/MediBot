"""Prueba el canal de Vonage SIN internet: simula lo que Vonage envía y captura lo que el bot respondería.
Uso:  python test_vonage.py"""
import base64
import os
import tempfile
from datetime import datetime

os.environ.update(DB_PATH=os.path.join(tempfile.mkdtemp(), "vonage.db"), MODO="vonage",
                  VONAGE_API_KEY="abc123", VONAGE_API_SECRET="secreto", VONAGE_WHATSAPP_NUMBER="14157386102")

import app as A
import mensajeria
import recordatorios as rec
import reloj

enviados = []
mensajeria._post = lambda url, datos, cab: (enviados.append((url, datos, cab)) or (202, '{"message_uuid":"x"}'))
c = A.app.test_client()
fallos = 0


def ok(cond, nombre):
    global fallos
    print("✅" if cond else "❌", nombre)
    fallos += 0 if cond else 1


def entrante(texto, uuid, numero="50371110776", tipo="text"):
    return {"channel": "whatsapp", "message_uuid": uuid, "to": "14157386102", "from": numero,
            "timestamp": "2026-10-09T12:00:00Z", "message_type": tipo, **({"text": texto} if tipo == "text" else {})}


r = c.post("/vonage/inbound", json=entrante("hola", "u1"))
ok(r.status_code == 200, "POST /vonage/inbound responde 200 (si no, Vonage reintenta)")
ok(len(enviados) == 1, "El bot envió 1 respuesta")
url, datos, cab = enviados[0]
ok(url == "https://messages-sandbox.nexmo.com/v1/messages", "Usa el endpoint del sandbox")
ok(datos["to"] == "50371110776" and datos["from"] == "14157386102", "Remitente y destinatario correctos (sin +)")
ok(datos["channel"] == "whatsapp" and datos["message_type"] == "text", "Canal y tipo de mensaje correctos")
ok("cómo te llamas" in datos["text"].lower(), "Primera respuesta: pregunta el nombre")
ok(cab["Authorization"] == "Basic " + base64.b64encode(b"abc123:secreto").decode(), "Autenticación con API key y secret")

c.post("/vonage/inbound", json=entrante("hola", "u1"))
ok(len(enviados) == 1, "Un mensaje repetido (reintento) no genera respuesta doble")

for i, t in enumerate(["Ana", "Tomo paracetamol 500 mg cada 8 horas a las 8am por 3 días", "1"], start=2):
    c.post("/vonage/inbound", json=entrante(t, f"u{i}"))
ok("Registré" in enviados[-1][1]["text"], "Registró el medicamento por el canal de Vonage")

estado = {"message_uuid": "z", "to": "50371110776", "from": "14157386102", "channel": "whatsapp", "status": "delivered"}
antes = len(enviados)
ok(c.post("/vonage/status", json=estado).status_code == 200, "El webhook de estado responde 200")
ok(c.post("/vonage/inbound", json=estado).status_code == 200 and len(enviados) == antes,
   "Una notificación de estado no genera respuesta")
c.post("/vonage/inbound", json=entrante("", "u9", tipo="image"))
ok("texto" in enviados[-1][1]["text"].lower(), "Una imagen recibe una respuesta amable")

reloj.fijar(datetime.now().replace(hour=7, minute=30, second=0))
reloj.avanzar(24 * 60)
antes = len(enviados)
rec.avanzar_tiempo(60)
nuevos = [e for e in enviados[antes:] if "Hora de tu medicina" in e[1]["text"]]
ok(len(nuevos) >= 1 and nuevos[0][1]["to"] == "50371110776", "El recordatorio sale por Vonage al número correcto")

print("\n" + ("🎉 Todo correcto" if not fallos else f"⚠️ {fallos} fallo(s)"))
raise SystemExit(1 if fallos else 0)
