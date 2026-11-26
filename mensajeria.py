"""mensajeria.py - Envío de mensajes de WhatsApp.  Un solo lugar para todos los canales.

  MODO=vonage -> Vonage Messages API (Sandbox o producción)
  MODO=twilio -> Twilio Sandbox
  MODO=local  -> no envía nada (el simulador web muestra los avisos)
"""
import base64
import json
import time
import urllib.error
import urllib.request
import uuid

import config


def solo_digitos(telefono):
    """'whatsapp:+503 7111-0776' -> '50371110776' (formato que pide Vonage: sin + ni 00)."""
    return "".join(c for c in (telefono or "") if c.isdigit())


def canal_real():
    return config.vonage_listo() or config.twilio_listo()


def enviar_texto(telefono, mensaje):
    """Devuelve True si el mensaje se envió."""
    if config.vonage_listo():
        return _enviar_vonage(telefono, mensaje)
    if config.twilio_listo():
        return _enviar_twilio(telefono, mensaje)
    return False


# ------------------------------------------------------------------ Vonage
def _post(url, datos, cabeceras):
    """Función aparte para poder simularla en las pruebas."""
    peticion = urllib.request.Request(url, data=json.dumps(datos).encode("utf-8"),
                                      headers=cabeceras, method="POST")
    with urllib.request.urlopen(peticion, timeout=15) as r:
        return r.status, r.read().decode("utf-8")


def _autorizacion_vonage():
    if config.VONAGE_API_KEY and config.VONAGE_API_SECRET:
        credencial = f"{config.VONAGE_API_KEY}:{config.VONAGE_API_SECRET}".encode()
        return "Basic " + base64.b64encode(credencial).decode()
    import jwt                                   # pip install PyJWT cryptography  (solo para JWT)
    with open(config.VONAGE_PRIVATE_KEY_PATH) as f:
        llave = f.read()
    ahora = int(time.time())
    token = jwt.encode({"application_id": config.VONAGE_APPLICATION_ID, "iat": ahora,
                        "jti": str(uuid.uuid4()), "exp": ahora + 600}, llave, algorithm="RS256")
    return f"Bearer {token}"


def _enviar_vonage(telefono, mensaje):
    datos = {"from": config.VONAGE_WHATSAPP_NUMBER, "to": solo_digitos(telefono),
             "channel": "whatsapp", "message_type": "text", "text": mensaje[:4000]}
    try:
        cabeceras = {"Content-Type": "application/json", "Accept": "application/json",
                     "Authorization": _autorizacion_vonage()}
        estado, _ = _post(config.vonage_url(), datos, cabeceras)
        return 200 <= estado < 300
    except urllib.error.HTTPError as e:
        cuerpo = e.read().decode("utf-8", "ignore")[:300]
        pistas = {401: "credenciales incorrectas (revisa VONAGE_API_KEY / VONAGE_API_SECRET)",
                  422: "el número no está en la lista permitida del sandbox, o pasaron más de 24 h sin que escribas al bot",
                  429: "límite del sandbox alcanzado (100 mensajes al mes, 1 por segundo)"}
        print(f"[vonage] Error {e.code}: {pistas.get(e.code, 'revisa la respuesta')} · {cuerpo}")
    except Exception as e:
        print(f"[vonage] No se pudo enviar: {e}")
    return False


def extraer_mensaje_vonage(carga):
    """Del JSON que manda Vonage saca (numero, texto, id, tipo), o None si no es un mensaje entrante
    (por ejemplo una notificación de estado)."""
    if not isinstance(carga, dict) or carga.get("channel") not in (None, "whatsapp"):
        return None
    if "status" in carga and "message_type" not in carga:
        return None
    origen = carga.get("from")
    if isinstance(origen, dict):
        origen = origen.get("number") or origen.get("id")
    if not origen:
        return None
    tipo = carga.get("message_type", "text")
    texto = carga.get("text", "")
    if isinstance(texto, dict):
        texto = texto.get("body", "")
    if tipo != "text" or not isinstance(texto, str):
        texto = ""
    return str(origen), texto, carga.get("message_uuid", ""), tipo


# ------------------------------------------------------------------ Twilio
def _enviar_twilio(telefono, mensaje):
    try:
        from twilio.rest import Client
        Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN).messages.create(
            body=mensaje, from_=config.a_whatsapp(config.TWILIO_PHONE_NUMBER),
            to=config.a_whatsapp(telefono))
        return True
    except Exception as e:
        print(f"[twilio] No se pudo enviar: {e}")
        return False
